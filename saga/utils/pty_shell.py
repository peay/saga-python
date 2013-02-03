
import re
import os

import saga.utils.pty_process
import saga.utils.logger

_PTY_TIMEOUT = 2.0
_SCHEMAS     = ['ssh', 'gsissh', 'fork']

IGNORE   = 0    # discard stdout / stderr
MERGED   = 1    # merge stdout and stderr
SEPARATE = 2    # fetch stdout and stderr individually (one more hop)
STDOUT   = 3    # fetch stdout only, discard stderr
STDERR   = 4    # fetch stderr only, discard stdout

# --------------------------------------------------------------------
#
class PTYShell (object) :
    """
    This class wraps a shell process and runs it as a :class:`PTYProcess`.  The
    user of this class can start that shell, and run arbitrary commands on it.

    The shell to be run is expected to be POSIX compliant (bash, csh, sh, zsh
    etc) -- in particular, we expect the following features:
    `$?`,
    `$!`,
    `$*`,
    `$#`,
    `$@`,
    `$PPID`,
    `>&`,
    `>>`,
    `>`,
    `<`,
    `2>&1`,
    `|`,
    `||`,
    `&&`,
    `wait`,
    `kill`,
    `nohup`, and
    `shift`

    Example::

        # start the shell, find its prompt.  
        self.shell = saga.utils.pty_shell.PTYShell ("ssh://user@remote.host.net/", contexts, self._logger)

        # run a simple shell command, merge stderr with stdout.  $$ is the pid
        # of the shell instance.
        ret, out, _ = self.shell.run_sync ("mkdir -p /tmp/data.$$/" )

        # check if mkdir reported success
        if  ret != 0 :
            raise saga.NoSuccess ("failed to prepare base dir (%s)(%s)" % (ret, out))

        # stage some data from a local string variable into a file on the remote system
        self.shell.stage_to_file (src = pbs_job_script, 
                                  tgt = "/tmp/data.$$/job_1.pbs")

        # check size of staged script
        ret, out, _ = self.shell.run_sync ("stat -c '%s' /tmp/data.$$/job_1.pbs" )
        if  ret != 0 :
            raise saga.NoSuccess ("failed to check size (%s)(%s)" % (ret, out))

        assert (len(pbs_job_script) == int(out))

    """

    # ----------------------------------------------------------------
    #
    def __init__ (self, url, contexts=[], logger=None) :

        self.url       = url               # describes the shell to run
        self.contexts  = contexts          # get security tokens from these
        self.logger    = logger            # possibly log to here
        self.prompt    = "^(.*[\$#>])\s*$" # a line ending with # $ >
        self.prompt_re = re.compile (self.prompt, re.DOTALL)
        
        # need a new logger?
        if not self.logger :
            self.logger = saga.utils.logger.getLogger ('PTYShell')

        schema  = self.url.schema.lower ()
        sh_type = ""
        sh_exe  = ""
        sh_pass = ""

        # find out what type of shell we have to deal with
        if  schema   == "ssh" :
            sh_type  =  "ssh"
            sh_exe   =  saga.utils.which.which ("ssh")

        elif schema  == "gsissh" :
            sh_type  =  "ssh"
            sh_exe   =  saga.utils.which.which ("gsissh")

        elif schema  == "fork" :

            sh_type  =  "sh"
            if  "SHELL" in os.environ :
                sh_exe =  saga.utils.which.which (os.environ["SHELL"])
            else :
                sh_exe =  saga.utils.which.which ("sh")
        else :
            raise saga.BadParameter._log (self.logger, \
            	  "PTYShell utility can only handle %s schema URLs, not %s" \
                  % (_SCHEMAS, schema))



        # make sure we have something to run
        if not sh_exe :
            raise saga.BadParameter._log (self.logger, \
            	  "adaptor cannot handle %s://, no shell exe found" % schema)


        # depending on type, create PTYProcess command line (args, env etc)
        #
        # We always set term=vt100 to avoid ansi-escape sequences in the prompt
        # and elsewhere.  Also, we have to make sure that the shell is an
        # interactive login shell, so that it interprets the users startup
        # files, and reacts on commands.
        if  sh_type == "ssh" :

            sh_env  =  "/usr/bin/env TERM=vt100 "  # avoid ansi escapes
            sh_args =  "-t "                       # force pty
            sh_user =  ""                          # use default user id

            for context in self.contexts :

                if  context.type.lower () == "ssh" :
                    # ssh can handle user_id and user_key of ssh contexts
                    if  schema == "ssh" :
                        if  context.attribute_exists ("user_id") :
                            sh_user  = context.user_id
                        if  context.attribute_exists ("user_key") :
                            sh_args += "-i %s " % context.user_key

                if  context.type.lower () == "userpass" :
                    # FIXME: ssh should also be able to handle UserPass contexts
                    if  schema == "ssh" :
                        pass

                if  context.type.lower () == "gsissh" :
                    # gsissh can handle user_proxy of X509 contexts
                    # FIXME: also use cert_dir etc.
                    if  context.attribute_exists ("user_proxy") :
                        if  schema == "gsissh" :
                            sh_env = "X509_PROXY='%s' " % context.user_proxy

            # all ssh based shells allow for user_id from contexts -- but the
            # username given in the URL takes precedence
            if self.url.username :
                sh_user = self.url.username

            if sh_user :
                sh_args += "-l %s " % sh_user

            # build the ssh command line
            sh_cmd  =  "%s %s %s %s" % (sh_env, sh_exe, sh_args, self.url.host)

        # a local shell
        elif sh_type == "sh" :
            # Make sure we have an interactive login shell w/o ansi escapes.
            sh_args =  "-l -i"
            sh_env  =  "/usr/bin/env TERM=vt100"
            sh_cmd  =  "%s %s %s" % (sh_env, sh_exe, sh_args)

        self.sh_type = sh_type
        self.sh_cmd  = sh_cmd

        # we got the shell command - now run it!
        self._open ()


    # ----------------------------------------------------------------
    #
    def __del__ (self) :

        self._close ()


    # ----------------------------------------------------------------
    #
    def _open (self) :
        """ 
        open the shell connection, as specified by URL and contexts.  The shell
        is run as a :class:`saga.utils.pty_process.PTYProcess` instance.
        """


        self.logger.info ("job service opens pty for '%s'" % self.sh_cmd)
        self.pty = saga.utils.pty_process.PTYProcess (self.sh_cmd, 
                                                      logger=self.logger)


        prompt_patterns = ["password\s*:\s*$",            # password prompt
                           "want to continue connecting", # hostkey confirmation
                           self.prompt]                   # native shell prompt 
        # FIXME: consider to not do hostkey checks at all (see ssh options)

        if self.sh_type == 'sh' :
            # self.prompt is all we need for local shell, but we keep the other
            # pattern around so that the switch in the while loop below is the
            # same for both shell types
            #
            # prompt_patterns = [self.prompt] 
            pass


        # run the shell and find prompt
        n, match = self.pty.find (prompt_patterns, _PTY_TIMEOUT)

        # this loop will run until we finally find the self.prompt.  At that
        # point, we'll try to set a different prompt, and when we found that,
        # too, we'll exit the loop and consider to be ready for running shell
        # commands.
        while True :

            # we found none of the prompts, yet -- try again if the shell still
            # lives.
            if n == None :
                if not self.pty.alive () :
                    raise saga.NoSuccess ("failed to start shell (%s)" % match)

                # the write below will make our live simpler, as it will
                # eventually flush I/O buffers, and will make sure that we
                # get a decent prompt -- no matter what stupi^H^H^H^H^H nice
                # PS1 the user invented...
                #
                # FIXME: make sure this does not interfere with the host
                # key and password prompts.  For ssh's, a simple '\n' might
                # suffice...
              # self.pty.write ("PS1='PROMPT-$?->\\n'\nexport PS1\n")
              # self.pty.write ("\n")
                n, match = self.pty.find (prompt_patterns, _PTY_TIMEOUT)


            if n == 0 :
                self.logger.debug ("got password prompt")
                if not sh_pass :
                    raise saga.NoSuccess ("prompted for unknown password (%s)" \
                                       % match)

                self.pty.write ("%s\n" % sh_pass)
                n, match = self.pty.find (prompt_patterns, _PTY_TIMEOUT)


            elif n == 1 :
                self.logger.debug ("got hostkey prompt")
                self.pty.write ("yes\n")
                n, match = self.pty.find (prompt_patterns, _PTY_TIMEOUT)


            elif n == 2 :
                self.logger.debug ("got initial shell prompt")

                # try to set new prompt
                self.run_sync ("PS1='PROMPT-$?->\\n'; export PS1\n", 
                                new_prompt="PROMPT-(\d+)->\s*$")
                self.logger.debug ("got new shell prompt")

                # we are done waiting for a prompt
                break
        

    # ----------------------------------------------------------------
    #
    def _close (self) :

        try :
            if self.pty : 
                del (self.pty)
        except Exception :
            pass


    # ----------------------------------------------------------------
    #
    def alive (self) :
        """
        alive() checks if the shell is still alive.  duh!
        """

        if self.pty and self.pty.alive () :
            return True

        return False
        

    # ----------------------------------------------------------------
    #
    def find_prompt (self) :
        """
        If run_async was called, a command is running on the shell.  find_prompt
        can be used to collect its output up to the point where the shell prompt
        re-appears (i.e. when the command finishes).

        Note that this method blocks until the command finishes.  Future
        versions of this call may add a timeout parameter.
        """

        _,   match = self.pty.find     ([self.prompt], _PTY_TIMEOUT)
        ret, txt   = self._eval_prompt (match)

        return (ret, txt)


    # ----------------------------------------------------------------
    #
    def set_prompt (self, prompt) :
        """
        :type  prompt:  string 
        :param prompt:  a regular expression matching the shell prompt

        The prompt regex is expected to be a regular expression with one set of
        catching brackets, which MUST return the previous command's exit status.
        This method will send a newline to the client, and expects to find the
        prompt with the exit value '0'.

        As a side effect, this method will discard all previous data on the pty,
        thus effectively flushing the pty output.  

        By encoding the exit value in the command prompt, we safe one roundtrip.
        The prompt on Posix compliant shells can be set, for example, via::

          PS1='PROMPT-$?->\\n'; export PS1

        The newline in the example above allows to nicely anchor the regular
        expression, which would look like::

          PROMPT-(\d+)->\s*$

        The regex is compiled with 're.DOTALL', so the dot character matches
        all characters, including line breaks.  Be careful not to match more
        than the exact prompt -- otherwise, a prompt search will swallow stdout
        data.  For example, the following regex::

          PROMPT-(.+)->\s*$

        would capture arbitrary strings, and would thus match *all* of::

          PROMPT-0-> ls
          data/ info
          PROMPT-0->

        and thus swallow the ls output...
        """

        old_prompt     = self.prompt
        self.prompt    = prompt
        self.prompt_re = re.compile ("^(.*)%s\s*$" % self.prompt, re.DOTALL)

        try :
            self.pty.write ("\n")

            # FIXME: how do we know that _PTY_TIMOUT suffices?  In particular if
            # we actually need to flush...
            _, match  = self.pty.find ([self.prompt], _PTY_TIMEOUT)

            if not match :
                self.prompt = old_prompt
                raise saga.BadParameter ("Cannot use prompt, could not find it")

            ret, _ = self._eval_prompt (match)

            if  ret != 0 :
                self.prompt = old_prompt
                raise saga.BadParameter ("could not parse exit value (%s)" \
                                      % match)

        except Exception as e :
            self.prompt = old_prompt
            raise saga.NoSuccess ("Could not set prompt (%s)" % e)



    # ----------------------------------------------------------------
    #
    def _eval_prompt (self, data, new_prompt=None) :
        """
        This method will match the given data against the current prompt regex,
        and expects to find an integer as match -- which is then returned, along
        with all leading data, in a tuple
        """

        prompt    = self.prompt
        prompt_re = self.prompt_re

        if  new_prompt :
            prompt    = new_prompt
            prompt_re = re.compile ("^(.*)%s\s*$" % prompt, re.DOTALL)

        result = None
        try :
            if  not data :
                raise saga.NoSuccess ("could not parse prompt on empty string (%s) (%s)" \
                                   % (prompt, data))

            result = prompt_re.match (data)

            if  not result :
                raise saga.NoSuccess ("could not parse prompt (%s) (%s)" \
                                   % (prompt, data))

            if  len (result.groups ()) != 2 :
                raise saga.NoSuccess ("prompt does not capture exit value (%s)"\
                                   % prompt)

            txt =     result.group (1)
            ret = int(result.group (2)) 

        except Exception as e :
            self.logger.debug ("data   : %s" % data)
            self.logger.debug ("prompt : %s" % prompt)

            if  result and len(result.groups()) == 2 :
                self.logger.debug ("match 1: %s" % result.group (1))
                self.logger.debug ("match 2: %s" % result.group (2))

            raise saga.NoSuccess ("Could not eval prompt (%s)" % e)


        # if that worked, we can permanently set new_prompt
        if  new_prompt :
            self.set_prompt (new_prompt)

        return (ret, txt)






    # ----------------------------------------------------------------
    #
    def run_sync (self, command, iomode=None, new_prompt=None) :
        """
        Run a shell command, and report exit code, stdout and stderr (all three
        will be returned in a tuple).  The call will block until the command
        finishes (more exactly, until we find the prompt again on the shell's IO
        stream), and cannot be interrupted.

        :type  command: string
        :param command: shell command to run.  
        
        :type  iomode:  enum
        :param iomode:  Defines how stdout and stderr are captured.  

        :type  new_prompt:  string 
        :param new_prompt:  regular expression matching the prompt after
        command succeeded.

        We expect the ``command`` to not to do stdio redirection, as this is we want
        to capture that separately.  We *do* allow pipes and stdin/stdout
        redirection.  Note that SEPARATE mode will break if the job is run in
        the background

        
        The following iomode values are valid:

          * *IGNORE:*   both stdout and stderr are discarded, `None` will be
                        returned for each.
          * *MERGED:*   both streams will be merged and returned as stdout; 
                        stderr will be `None`.  This is the default.
          * *SEPARATE:* stdout and stderr will be captured separately, and
                        returned individually.  Note that this will require 
                        at least one more network hop!  
          * *STDOUT:*   only stdout is captured, stderr will be `None`.
          * *STDERR:*   only stderr is captured, stdout will be `None`.
          * *None:*     do not perform any redirection -- this is effectively
                        the same as `MERGED`

        If any of the requested output streams does not return any data, an
        empty string is returned.

        
        If the command to be run changes the prompt to be expected for the
        shell, the ``new_prompt`` parameter MUST contain a regex to match the
        new prompt.  The same conventions as for set_prompt() hold -- i.e. we
        expect the prompt regex to capture the exit status of the process.
        """

        command = command.strip ()
        if command.endswith ('&') :
            raise saga.BadParameter ("can only run foreground jobs ('%s')" \
                                  % command)

        redir = ""
        _err  = "/tmp/saga-python.ssh-job.stderr.$$"

        if  iomode == IGNORE :
            redir  =  " 1>>/dev/null 2>>/dev/null"

        if  iomode == MERGED :
            redir  =  " 2>&1"

        if  iomode == SEPARATE :
            redir  =  " 2>%s" % _err

        if  iomode == STDOUT :
            redir  =  " 2>/dev/null"

        if  iomode == STDERR :
            redir  =  " 2>&1 1>/dev/null"

        if  iomode == None :
            redir  =  ""

        self.pty.write ("%s%s\n" % (command, redir))


        # If given, switch to new prompt pattern right now...
        prompt = self.prompt
        if  new_prompt :
            prompt = new_prompt

        # command has been started - now find prompt again.  
        _, match = self.pty.find ([prompt], timeout=-1.0)  # blocks

        if not match :
            # not find prompt after blocking?  BAD!  Restart the shell
            self._close ()
            raise saga.NoSuccess ("run_sync failed, no prompt (%s)" % command)


        ret, txt = self._eval_prompt (match, prompt)

        stdout = None
        stderr = None

        if  iomode == IGNORE :
            pass

        if  iomode == MERGED :
            stdout =  txt

        if  iomode == SEPARATE :
            stdout =  txt

            self.pty.write ("cat %s\n" % _err)
            _, match = self.pty.find ([self.prompt], timeout=-1.0)  # blocks

            if not match :
                # not find prompt after blocking?  BAD!  Restart the shell
                self._close ()
                raise saga.NoSuccess ("run_sync failed, no prompt (%s)" \
                                    % command)

            _ret, _stderr = self._eval_prompt (match)
            if  _ret :
                raise saga.NoSuccess ("run_sync failed, no stderr (%s: %s)" \
                                   % (_ret, _stderr))
            stderr =  _stderr


        if  iomode == STDOUT :
            stdout =  txt

        if  iomode == STDERR :
            stderr =  txt

        if  iomode == None :
            stdout =  txt


        return (ret, stdout, stderr)


    # ----------------------------------------------------------------
    #
    def run_async (self, command) : 
        """ Run a shell command, but don't wait for prompt -- just return.  It
        is up to caller to eventually search for the prompt again (see
        :func:`find_prompt`.  Meanwhile, the caller can interact with the called
        command, via the io channels.

        :type  command: string
        :param command: shell command to run.  
        
        For async execution, we don't care if the command is doing i/o redirection or not.
        """

        command = command.strip ()
        self.pty.write ("%s\n" % command)

        return


    # ----------------------------------------------------------------
    #
    def stage_to_file (self, src, tgt) :
        """
        :type  src: string
        :param src: data to be staged into the target file

        :type  tgt: string
        :param tgt: path to file to be staged

        The content of the given string is pasted into a file (specified by tgt)
        on the remote system.  If that file exists, it is overwritten.
        A NoSuccess exception is raised if writing the file was not possible
        (missing permissions, incorrect path, etc.).

        See also :func:`stage_from_file`.
        """

        self.run_async ("cat > %s" % tgt)
        self.pty.write (src)
        self.pty.write ("\n\4")  # send CTRL-D

        ret, txt = self.find_prompt ()

        if  ret != 0 :
            raise saga.NoSuccess ("failed to stage string to file (%s)(%s)" % (ret, txt))

    # ----------------------------------------------------------------
    #
    def stage_from_file (self, src) :
        """
        :type  src: string
        :param src: path to file to be fetched

        This is inverse to :func:`stage_to_file`: the content of a remote file
        specified by `src` will be returned as string.  A NoSuccess exception is
        raised if reading the file was not possible (missing permissions,
        incorrect path, etc.).  
        """

        ret, out, _ = self.run_sync ("cat %s" % src)

        if  ret != 0 :
            raise saga.NoSuccess ("failed to stage file to string (%s)(%s)" % (ret, out))

        return out


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

