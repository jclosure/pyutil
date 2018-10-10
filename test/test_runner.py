import multiprocessing
from multiprocessing import Manager
from unittest import TestCase

from pyutil.sql.base import Base
from pyutil.sql.interfaces.symbols.strategy import Strategy
from pyutil.runner import Runner
from pyutil.sql.session import postgresql_db_test

class WorkerImpl1(multiprocessing.Process):
    def __init__(self, name, x):
        super().__init__(name=name)
        self.x = x

    def run(self):
        assert False


class WorkerImpl2(multiprocessing.Process):
    def __init__(self, name, x):
        super().__init__(name=name)
        self.x = x

    def run(self):
        assert True


class RunnerImpl(Runner):
    def __init__(self, sql=None, influxdb=None):
        super().__init__(sql, influxdb)
        manager = Manager()
        self.__dict = manager.dict()

    def target(self, strategy_id):
        with self.session() as session:
            s = session.query(Strategy).filter_by(id=strategy_id).one()
            self.__dict[s.name] = s.name
            print(s)

    @property
    def dict(self):
        return self.__dict



class TestRunner(TestCase):
    def test_Runner_Faulty(self):
        runner = Runner()

        # worker will raise an Exception!
        with self.assertRaises(AssertionError):
            runner.jobs.append(WorkerImpl1(name="Peter", x=10))
            runner.run_jobs()

    def test_Runner_Correct(self):
        runner = Runner()

        # worker will not raise an Exception!
        runner.jobs.append(WorkerImpl2(name="Peter", x=10))
        runner.run_jobs()

    def test_Runner_empty(self):
        runner = Runner()

        self.assertListEqual(runner.jobs, [])
        # this won't do any harm
        runner.run_jobs()

