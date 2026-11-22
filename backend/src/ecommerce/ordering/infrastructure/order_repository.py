from uuid import UUID

from sqlalchemy import RowMapping, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.ordering.domain.events import OrderEvent
from ecommerce.ordering.domain.order import Order, OrderId, OrderLine
from ecommerce.ordering.domain.value_objects import Customer, OrderStatus
from ecommerce.ordering.infrastructure.tables import order_lines, orders
from ecommerce.shared_kernel.domain.money import Money


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._stored_events: list[OrderEvent] = []

    def take_stored_events(self) -> list[OrderEvent]:
        events, self._stored_events = self._stored_events, []
        return events

    def forget_stored_events(self) -> None:
        self._stored_events = []

    async def add(self, order: Order) -> None:
        await self._session.execute(
            insert(orders).values(
                id=order.id,
                status=order.status.value,
                customer_name=order.customer.name,
                customer_email=order.customer.email,
                total=order.total.amount,
                payment_reference=order.payment_reference,
                card_last4=order.card_last4,
                decline_reason=order.decline_reason,
                created_at=order.created_at,
                settled_at=order.settled_at,
                buyer_id=order.buyer_id,
            )
        )
        await self._session.execute(
            insert(order_lines),
            [
                {
                    "order_id": order.id,
                    "sku": line.sku,
                    "product_id": line.product_id,
                    "name": line.name,
                    "unit_price": line.unit_price.amount,
                    "quantity": line.quantity,
                    "gift": line.gift,
                    "line_total": line.line_total.amount,
                }
                for line in order.lines
            ],
        )
        self._stored_events.extend(order.pull_events())

    async def get(self, order_id: OrderId) -> Order | None:
        row = (
            (await self._session.execute(select(orders).where(orders.c.id == order_id)))
            .mappings()
            .first()
        )
        if row is None:
            return None
        lines = (
            (
                await self._session.execute(
                    select(order_lines)
                    .where(order_lines.c.order_id == order_id)
                    .order_by(order_lines.c.sku)
                )
            )
            .mappings()
            .all()
        )
        return to_order(row, [to_line(line) for line in lines])

    async def for_buyer(
        self, buyer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Order], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(orders).where(orders.c.buyer_id == buyer_id)
        )
        rows = (
            (
                await self._session.execute(
                    select(orders)
                    .where(orders.c.buyer_id == buyer_id)
                    .order_by(orders.c.created_at.desc(), orders.c.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )
        ids = [row["id"] for row in rows]
        lines: dict[UUID, list[OrderLine]] = {order_id: [] for order_id in ids}
        if ids:
            line_rows = (
                (
                    await self._session.execute(
                        select(order_lines)
                        .where(order_lines.c.order_id.in_(ids))
                        .order_by(order_lines.c.sku)
                    )
                )
                .mappings()
                .all()
            )
            for line in line_rows:
                lines[line["order_id"]].append(to_line(line))
        return [to_order(row, lines[row["id"]]) for row in rows], int(total or 0)


def to_line(row: RowMapping) -> OrderLine:
    return OrderLine(
        sku=row["sku"],
        product_id=row["product_id"],
        name=row["name"],
        unit_price=Money(row["unit_price"]),
        quantity=row["quantity"],
        gift=row["gift"],
    )


def to_order(row: RowMapping, lines: list[OrderLine]) -> Order:
    return Order(
        order_id=OrderId(row["id"]),
        customer=Customer(name=row["customer_name"], email=row["customer_email"]),
        lines=lines,
        status=OrderStatus(row["status"]),
        created_at=row["created_at"],
        settled_at=row["settled_at"],
        payment_reference=row["payment_reference"],
        card_last4=row["card_last4"],
        decline_reason=row["decline_reason"],
        buyer_id=row["buyer_id"],
    )
