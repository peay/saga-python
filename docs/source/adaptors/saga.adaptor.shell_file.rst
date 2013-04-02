
#######################
saga.adaptor.shell_file
#######################

Description
-----------
 
The shell file adaptor. This adaptor uses the sh command line tools (sh,
ssh, gsissh) to access remote filesystems.




Supported Schemas
-----------------

This adaptor is triggered by the following URL schemes:

======================== ============================================================
schema                   description                                                 
======================== ============================================================
**file://**              use /bin/sh to access local filesystems                     
**sftp://**              use sftp to access remote filesystems                       
**local://**             alias for file://                                           
**gsiftp://**            use gsiftp to access remote filesystems                     
======================== ============================================================



Example
-------

.. literalinclude:: ../../../NO EXAMPLE AVAILABLE


Configuration Options
---------------------
Configuration options can be used to control the adaptor's runt    ime behavior. Most adaptors don't need any configuration options to b    e set in order to work. They are mostly for controlling experimental feat    ures and properties of the adaptors.

     .. s    eealso:: More information about configuration options can be found in the     :ref:`conf_file` section.

enabled
*******

enable / disable saga.adaptor.shell_file adaptor

  - **type** : <type 'bool'>
  - **default** : True
  - **environment** : None
  - **valid options** : [True, False]
enable_notifications
********************

Enable support for filesystem notifications.  Note that
enabling this option will create a local thread and a remote 
shell process.


  - **type** : <type 'bool'>
  - **default** : False
  - **environment** : None
  - **valid options** : [True, False]


Capabilities
------------

Supported Monitorable Metrics
*****************************


Supported Context Types
***********************

========================= ============================================================
                Attribute Description
========================= ============================================================
                     x509 X509 proxy for gsissh
                 userpass username/password pair for ssh
                      ssh public/private keypair
========================= ============================================================



Supported API Classes
---------------------

This adaptor supports the following API classes:
  - :class:`saga.namespace.Directory`
  - :class:`saga.namespace.Entry`
  - :class:`saga.filesystem.Directory`
  - :class:`saga.filesystem.File`

Method implementation details are listed below.

saga.namespace.Directory
************************

.. autoclass:: saga.adaptors.shell.shell_file.ShellDirectory
   :members:


saga.namespace.Entry
********************

.. autoclass:: saga.adaptors.shell.shell_file.ShellFile
   :members:


saga.filesystem.Directory
*************************

.. autoclass:: saga.adaptors.shell.shell_file.ShellDirectory
   :members:


saga.filesystem.File
********************

.. autoclass:: saga.adaptors.shell.shell_file.ShellFile
   :members:


