import abc
import logging
import os

from sqlalchemy import create_engine


class Runner(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, connection_str, logger=None):
        self._connection_str = connection_str
        self._logger = logger or logging.getLogger(__name__)
        self.__jobs = []

    @property
    def _engine(self):
        """ Create a fresh new session... """
        #self._engine.dispose()
        return create_engine(self._connection_str, echo=False)
        #conn = engine.connect()
        #return engine
        #factory = sessionmaker(self.__engine)
        #return factory()

    def _run_jobs(self):
        self._logger.debug("PID main {pid}".format(pid=os.getpid()))

        for job in self.jobs:
            # all jobs get the trigge
            self._logger.info("Job {j}".format(j=job.name))
            job.start()

        for job in self.jobs:
            self._logger.info("Wait for job {j}".format(j=job.name))
            job.join()
            self._logger.info("Job {j} done".format(j=job.name))

    @property
    def jobs(self):
        return self.__jobs

    @abc.abstractmethod
    def run(self):
        """ Described in the child class """

