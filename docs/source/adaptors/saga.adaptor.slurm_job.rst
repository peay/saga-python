
######################
saga.adaptor.slurm_job
######################

Description
-----------
 
The SLURM adaptor allows to run and manage jobs on a 
`SLURM <https://computing.llnl.gov/linux/slurm/slurm.html>`_ HPC cluster.

General Notes
*************

On Stampede, returning a non-zero exit code results in the scheduler
putting the job into a FAILED state and assigning it an exit code of 127.

**Example:**

::

  js = saga.job.Service("slurm+ssh://stampede")
  jd.executable  = '/bin/exit'
  jd.arguments   = ['3']
  job = js.create_job(jd)
  job.run()

Will return something similar to (personal account information
removed)::

  (saga-python-env)ashleyz@login1:~$ scontrol show job 309684
  JobId=309684 Name=SlurmJob
     UserId=_____ GroupId=__________
     Priority=3000 Account=_____ QOS=normal
     JobState=FAILED Reason=NonZeroExitCode Dependency=(null)
     Requeue=0 Restarts=0 BatchFlag=1 ExitCode=127:0
     RunTime=00:00:05 TimeLimit=00:01:00 TimeMin=N/A
     SubmitTime=2013-02-22T20:26:50 EligibleTime=2013-02-22T20:26:50
     StartTime=2013-02-22T20:26:50 EndTime=2013-02-22T20:26:55
     PreemptTime=None SuspendTime=None SecsPreSuspend=0
     Partition=development AllocNode:Sid=login1:12070
     ReqNodeList=(null) ExcNodeList=(null)
     NodeList=c557-401
     BatchHost=c557-401
     NumNodes=1 NumCPUs=16 CPUs/Task=1 ReqS:C:T=*:*:*
     MinCPUsNode=1 MinMemoryNode=0 MinTmpDiskNode=0
     Features=(null) Gres=(null) Reservation=(null)
     Shared=0 Contiguous=0 Licenses=(null) Network=(null)
     Command=/home1/01414/_______/.saga/adaptors/slurm_job/wrapper.sh
     WorkDir=/home1/01414/_______/

I'm not sure how to fix this for the time being.

Suspend/resume do not appear to be supported for regular
users on Stampede.

run_job is not supported, as there are many attributed (queues,
projects, etc) which need to be passed to the adaptor.  I could
add URL parsing so that you could pile on queue/project/jobname
information if this has any strong usecases, but I avoided doing
so for now to decrease complexity/possible confusion.

Cancelling a job with scontrol, puts it into a COMPLETING state, which
is parsed by the SLURM status parser as saga.job.RUNNING (see the
SLURM docs, COMPLETING is a state a job goes into when it is done
running but still flushing IO/etc).  Anyhow, I put some code in to
manually put the job into CANCELED state when the job is canceled,
but I'm not sure that this is reported correctly everywhere yet.

What exit code should be returned for a CANCELED job?

Implementation Notes
********************

 - If scontrol can't find an exit code, it returns None
   (see _job_get_exit_code)
 - If scancel can't cancel a job, we raise an exception
   (see _job_cancel)
 - If we can't suspend a job with scontrol suspend, we raise an exception
   (see _job_suspend).  scontrol suspend NOT supported on Stampede
 - I started to implement a dictionary to keep track of jobs locally.
   It works to the point where the unit tests are passed, but I have
   not gone over theis extensively...
 - Relating to the above, _job_get_info is written, but unused/untested
   (mostly from PBS adaptor)





Supported Schemas
-----------------

This adaptor is triggered by the following URL schemes:

======================== ============================================================
schema                   description                                                 
======================== ============================================================
**slurm://**             connect to a local cluster                                  
**slurm+ssh://**         conenct to a remote cluster via SSH                         
**slurm+gsissh://**      connect to a remote cluster via GSISSH                      
======================== ============================================================



Example
-------

.. literalinclude:: ../../../examples/jobs/slurmjob.py


Configuration Options
---------------------
Configuration options can be used to control the adaptor's runt    ime behavior. Most adaptors don't need any configuration options to b    e set in order to work. They are mostly for controlling experimental feat    ures and properties of the adaptors.

     .. s    eealso:: More information about configuration options can be found in the     :ref:`conf_file` section.

enabled
*******

enable / disable saga.adaptor.slurm_job adaptor

  - **type** : <type 'bool'>
  - **default** : True
  - **environment** : None
  - **valid options** : [True, False]


Capabilities
------------

Supported Monitorable Metrics
*****************************

  - State
  - StateDetail

Supported Job Attributes
************************

  - ExitCode
  - ExecutionHosts
  - Created
  - Started
  - Finished

Supported Context Types
***********************

========================= ============================================================
                Attribute Description
========================= ============================================================
                     x509 X509 proxy for gsissh
                 userpass username/password pair for simple ssh
                      ssh public/private keypair
========================= ============================================================

Supported Job Description Attributes
************************************

  - Name
  - Executable
  - Arguments
  - Environment
  - SPMDVariation
  - TotalCPUCount
  - NumberOfProcesses
  - ProcessesPerHost
  - ThreadsPerProcess
  - WorkingDirectory
  - Input
  - Output
  - Error
  - FileTransfer
  - Cleanup
  - JobStartTime
  - WallTimeLimit
  - TotalPhysicalMemory
  - Queue
  - Project
  - JobContact



Supported API Classes
---------------------

This adaptor supports the following API classes:
  - :class:`saga.job.Service`
  - :class:`saga.job.Job`

Method implementation details are listed below.

saga.job.Service
****************

.. autoclass:: saga.adaptors.slurm.slurm_job.SLURMJobService
   :members:


saga.job.Job
************

.. autoclass:: saga.adaptors.slurm.slurm_job.SLURMJob
   :members:


