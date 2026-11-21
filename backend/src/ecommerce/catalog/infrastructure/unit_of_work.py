from ecommerce.catalog.domain.repository import ProductRepository
from ecommerce.catalog.infrastructure.product_repository import SqlAlchemyProductRepository
from ecommerce.shared_kernel.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyCatalogUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def products(self) -> ProductRepository:
        return SqlAlchemyProductRepository(self.session)
