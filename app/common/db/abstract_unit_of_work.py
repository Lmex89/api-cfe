import abc


class AbstractUnitOfWork(abc.ABC):
    @abc.abstractmethod
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    @abc.abstractmethod
    def commit(self):
        self.session.commit()

    @abc.abstractmethod
    def rollback(self):
        self.session.rollback()
