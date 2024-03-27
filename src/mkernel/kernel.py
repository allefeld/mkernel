"""MKernel: A Jupyter Kernel for Matlab

kernel implementation

Copyright © 2023–2024 Carsten Allefeld
SPDX-License-Identifier: GPL-3.0-or-later
"""

__version__ = '1.1.0'


from os import path, environ
from io import StringIO
import re
from base64 import encodebytes
import gc

from ipykernel.kernelbase import Kernel
import matlab
import matlab.engine
try:
    from wurlitzer import pipes
except ModuleNotFoundError:
    # wurlitzer cannot be imported on Windows
    # see https://github.com/minrk/wurlitzer/issues/12
    pipes = None

from .json_logging import getJSONLogger, selfless


_get_check_set = '''
%% plot backend
MKernel_plot_backend = lower(string(getappdata(0, "MKernel_plot_backend")));
if isempty(MKernel_plot_backend)
    MKernel_plot_backend = "inline";        %% default
end
setappdata(0, "MKernel_plot_backend", MKernel_plot_backend);
assert(ismember(MKernel_plot_backend, ["inline", "native"]), ...
    "Unknown plot backend '%s'", MKernel_plot_backend)
%% plot format
MKernel_plot_format = lower(string(getappdata(0, "MKernel_plot_format")));
if isempty(MKernel_plot_format)
    MKernel_plot_format = "png";            %% default
end
setappdata(0, "MKernel_plot_format", MKernel_plot_format);
MKernel__formats = struct(png="png", svg="svg", jpeg="jpg", ...
    tiff="tiff", tiffn="tiff", meta="emf", pdf="pdf", eps="eps", ...
    epsc="eps", eps2="eps", eps2c="eps");
assert(isfield(MKernel__formats, MKernel_plot_format), ...
    "Unknown plot format '%s'", MKernel_plot_format)
%% plot resolution
MKernel_plot_resolution = getappdata(0, "MKernel_plot_resolution");
if isempty(MKernel_plot_resolution)
    MKernel_plot_resolution = get(0, "ScreenPixelsPerInch");
end
setappdata(0, "MKernel_plot_resolution", MKernel_plot_resolution);
assert(isnumeric(MKernel_plot_resolution) ...
    && (numel(MKernel_plot_resolution) == 1) ...
    && (MKernel_plot_resolution > 0) ...
    && (round(MKernel_plot_resolution) == MKernel_plot_resolution), ...
    "Invalid plot resolution, must be positive integer scalar")
%% output capture
MKernel_output_capture = lower(string(...
    getappdata(0, "MKernel_output_capture")));
if isempty(MKernel_output_capture)
    MKernel_output_capture = "auto";        %% default
end
setappdata(0, "MKernel_output_capture", MKernel_output_capture);
assert(ismember(MKernel_output_capture, ["auto", "wrapper", "engine"]), ...
    "Unknown output capture '%s'", MKernel_output_capture)
'''

_prepare_execution = _get_check_set + '''
%% set visibility of figure windows
set(0, "defaultFigureVisible", ~isequal(MKernel_plot_backend, "inline"))
%% cleanup
clear -regexp ^MKernel_
'''

_write_plots = _get_check_set + '''
%% only for "inline" plot backend: write plots
if isequal(MKernel_plot_backend, "inline")
    %% turn MATLAB:print:ExcludesUIInFutureRelease warning off
    ws = warning('query', 'MATLAB:print:ExcludesUIInFutureRelease');
    warning('off', 'MATLAB:print:ExcludesUIInFutureRelease')
    %% create temporary directory
    MKernel__tmpdir = tempname;
    mkdir(MKernel__tmpdir)
    %% get figure windows in order of creation
    MKernel__children = flipud(get(0, "children"));
    %% iterate over figure windows
    for MKernel__index = 1 : numel(MKernel__children)
        MKernel__handle = MKernel__children(MKernel__index);
        %% fix that default for pdf is full-page
        if isequal(MKernel_plot_format, "pdf")
            MKernel__handle.PaperPosition = ...
                [0 0 MKernel__handle.PaperPosition(3:4)];
            MKernel__handle.PaperSize = MKernel__handle.PaperPosition(3:4);
        end
        %% print figure to temporary file and output file name
        MKernel__filename = ...
            fullfile(MKernel__tmpdir, num2str(MKernel__index, "%06d"));
        try
            print(MKernel__handle, ...
                MKernel__filename, ...
                sprintf("-d%s", MKernel_plot_format), ...
                sprintf("-r%d", MKernel_plot_resolution))
            MKernel__extension = getfield(MKernel__formats, ...
                MKernel_plot_format);
            fprintf("%s.%s\\n", MKernel__filename, MKernel__extension)
        catch ME
            fprintf(2, "\\n  Figure %d: %s", MKernel__handle.Number, ...
                ME.message)
        end
        %% close figure so it isn't printed again with the next cell
        close(MKernel__handle)
    end
    %% restore state of MATLAB:print:ExcludesUIInFutureRelease
    warning(ws)
end
%% cleanup
clear -regexp ^MKernel_
'''


class MKernel(Kernel):
    implementation = 'MKernel'
    implementation_version = __version__
    language = 'MATLAB'
    language_info = {
        'name': 'matlab',
        'mimetype': 'text/x-matlab',
        'file_extension': '.m',
    }

    # regular expression for tokenization
    _re_tokens = re.compile(r"([a-zA-Z_0-9\.]*"         # identifiers & numbers
                            r"|\n+"                     # line breaks
                            r"|[^a-zA-Z_0-9\.\n]+)")    # everything else

    def __init__(self, **kwargs):
        # execute superclass constructor
        super().__init__(**kwargs)
        self.log = getJSONLogger('mkernel')
        # signal presence of kernel through environment variable
        environ['MKERNEL'] = self.implementation_version
        # announce communications handler
        self.shell_handlers['comm_open'] = self._comm
        # initialize Matlab
        self._init_matlab()

    def _init_matlab(self):
        # start Matlab engine
        self.log.info('starting Matlab engine')
        try:
            self._matlab = matlab.engine.start_matlab()
            self.language_version = self._matlab.version()
        except Exception as e:
            self.log.critical('could not start Matlab engine', exc_info=e)
            raise
        version = 'MATLAB ' + self.language_version
        self.banner = 'MKernel: ' + version
        self.log.info(f'started {version}')

    def _comm(self, stream, ident, msg):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#custom-messages
        # handle communications
        if msg['content']['target_name'] == "quarto_kernel_setup":
            o = msg['content']['data']['options']
            self.log.info('received Quarto communication', extra=o)
            # receive Quarto document options & convert to Matlab settings
            # <https://quarto.org/docs/advanced/jupyter/kernel-execution.html>
            # `fig-format`
            try:
                self._matlab.setappdata(
                    0., 'MKernel_plot_format',
                    o['fig_format'] if o['fig_format'] != 'retina' else 'svg',
                    nargout=0)
            except Exception as e:
                self.log.error('exception in Matlab engine', exc_info=e)
            # `fig-dpi`
            try:
                self._matlab.setappdata(
                    0., 'MKernel_plot_resolution', o['fig_dpi'],
                    nargout=0)
            except Exception as e:
                self.log.error('exception in Matlab engine', exc_info=e)
            # `fig-width` & `fig-height`
            try:
                self._matlab.set(
                    0., 'defaultFigurePaperUnits', 'inches',
                    nargout=0)
                self._matlab.set(
                    0., 'defaultFigurePaperPosition',
                    matlab.double([0., 0., o['fig_width'], o['fig_height']]),
                    nargout=0)
                self._matlab.set(
                    0., 'defaultFigurePaperPositionMode', 'manual',
                    nargout=0)
            except Exception as e:
                self.log.error('exception in Matlab engine', exc_info=e)
            # There is also `allow_errors` with default `false`.
            # Do we want this, especially as a default?
            # Also unclear how to implement it.

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False, cell_id=None):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#execute
        self.log.info('called with', extra=selfless(locals()))
        # prepare reply
        reply = {
            'status': 'ok',
            'execution_count': self.execution_count,
            'payload': [],
            'user_expressions': {}
            }
        # check for Quarto setup cell
        # see <https://github.com/quarto-dev/quarto-cli/issues/9100>
        if code.startswith(r"% setup 2d7a65c64eb8bb2b9cba670d8e11cef1"):
            # respond to cell
            self.log.info('responding to Quarto setup', extra={'reply': reply})
            self.send_response(
                self.iopub_socket,
                'execute_result', {
                    "data": {"text/plain": ""},
                    "metadata": {'quarto': {'daemonize': True}},
                    'execution_count': self.execution_count,
                })
            # do not execute the cell
            return reply
        # prepare execution
        self.log.debug('preparing execution')
        stderr = StringIO()
        try:
            self._matlab.eval(_prepare_execution, nargout=0, stderr=stderr)
        except Exception as e:
            self.log.error('exception in Matlab engine', exc_info=e)
            self._send_text('stderr', f'MKernel: {e.args[0]}')
        # execute code
        stdout = StreamIO(self, 'stdout', silent)
        stderr = StreamIO(self, 'stderr', silent)
        # StreamIO objects automatically send everything written to them
        try:
            capture = self._matlab.getappdata(0., 'MKernel_output_capture')
        except Exception as e:
            self.log.error('exception in Matlab engine', exc_info=e)
            capture = 'auto'
        if capture == 'auto':
            capture = 'wrapper' if allow_stdin else 'engine'
        if pipes is None:
            # wurlitzer cannot be imported on Windows
            capture = 'engine'
        self.log.debug(f'executing code, capture = {repr(capture)}')
        try:
            if capture == 'engine':
                # output captured by engine
                # `StreamIO.write` gets called once
                self._matlab.eval(code, nargout=0,
                                  stdout=stdout, stderr=stderr)
            else:
                # output captured outside of engine
                # `StreamIO.write` gets called for each output
                with pipes(stdout=stdout, stderr=stderr):
                    self._matlab.eval(code, nargout=0)
        except (SyntaxError, matlab.engine.MatlabExecutionError):
            # Occurs when there's an error in Matlab.
            # The error message gets passed to the user via stderr
            pass
        except matlab.engine.InterruptedError as e:
            self.log.warning('Matlab stopped by user, restarting', exc_info=e)
            # Occurs when the user issues `quit` or `exit`. Since it is not
            # possible to shut down the kernel from within the kernel such that
            # the client is notified, there will be another prompt. However,
            # any further code execution leads to an exception, because the
            # Matlab engine has been stopped. Therefore the engine needs to be
            # restarted.
            self._send_text(
                'stderr',
                'MKernel does not support `quit` or `exit`.\n'
                'To shut down the kernel in the console, press Ctrl-D.\n'
                'To shut down the kernel in a notebook, stop the notebook.\n'
                'Restarting Matlab.\n')
            try:
                # trigger finalizing the engine object
                del self._matlab
                gc.collect()
            except matlab.engine.SystemError:
                # Unavoidably occurs when the garbage collector finalizes the
                # engine object, which calls the `.exit()` method on it, which
                # fails because the engine is already stopped.
                pass
            # create new engine
            self._init_matlab()
        except Exception as e:
            self.log.error('exception in Matlab engine', exc_info=e)
        # write plots
        self.log.debug('writing plots')
        stdout = StringIO()
        stderr = StringIO()
        try:
            # get filenames
            self._matlab.eval(_write_plots, nargout=0,
                              stdout=stdout, stderr=stderr)
            filenames = stdout.getvalue().split()
            ploterrors = stderr.getvalue()
        except Exception as e:
            self.log.error('exception', exc_info=e)
            self._send_text('stderr', f'MKernel: {e.args[0]}')
            filenames = []
            ploterrors = []
        if len(ploterrors) > 0:
            self._send_text('stderr',
                            f'MKernel: Errors saving plots.{ploterrors}')
        # process plots
        self.log.debug('processing plots')
        mimetype = {
            '.jpg': 'image/jpeg',
            '.png': 'image/png',
            '.tif': 'image/tiff',
            '.emf': 'application/emf',
            '.pdf': 'application/pdf',
            '.eps': 'application/postscript',
            '.svg': 'image/svg+xml',
        }
        for filename in filenames:
            self.log.debug(f'sending plot {repr(filename)}')
            _, extension = path.splitext(filename)
            with open(filename, 'rb') as f:
                data = f.read()
            self._send_data(mimetype[extension], data)
        # return reply
        self.log.info('returning', extra={'reply': reply})
        return reply

    def _send_text(self, name, text):
        """send text to named stream"""
        self.send_response(
            self.iopub_socket,
            'stream',
            {
                'name': name,
                'text': text
            })

    def _send_data(self, mimetype, data):
        """send `bytes` as mimetype"""
        try:
            data = data.decode('utf-8')
        except Exception:
            data = encodebytes(data)
            data = data.decode('utf-8')
        self.send_response(
            self.iopub_socket,
            'display_data',
            {
                'data': {mimetype: data},
                'metadata': {}
            })

    def do_complete(self, code, cursor_pos):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#completion
        self.log.info('called with', extra=selfless(locals()))
        # get tab completions from undocumented Java method
        #   com.mathworks.jmi.MatlabMCR().mtFindAllTabCompletions()
        # The only way to call this method which seems to be working is to
        # execute `javaObject` and `javaMethod` within `eval`d Matlab code.
        # This poses the problem to convert the `code` string into a Matlab
        # expression which reproduces that string, as an argument to
        # `javaMethod`.
        escaped_code = code.replace("'", "''")
        escaped_code = ("[" + ", newline, ".join(
            [f"'{line}'"
             for line in escaped_code.split('\n')])
             + "]")
        # The wrapping `string` function converts the java.lang.String array
        # returned by the method to a Matlab string array, which is in turn
        # returned as a list of `str` by `eval`.
        try:
            matches = self._matlab.eval(
                "string(javaMethod('mtFindAllTabCompletions', "
                + "javaObject('com.mathworks.jmi.MatlabMCR'), "
                + escaped_code + ", "
                + f'{cursor_pos}, 0))')
        except Exception as e:
            self.log.error('exception in Matlab engine', exc_info=e)
            matches = []
        if isinstance(matches, str):
            matches = [matches]
        self.log.debug('mtFindAllTabCompletions', extra={'matches': matches})
        # how much of the completions is already there before `cursor_pos`?
        prefix = path.commonprefix([match.lower() for match in matches])
        before = code[:cursor_pos].lower()
        num_before = 0
        for i in reversed(range(len(prefix) + 1)):
            if before.endswith(prefix[:i]):
                num_before = i
                break
        reply = {
            'status': 'ok',
            'matches': matches,
            'cursor_start': cursor_pos - num_before,
            'cursor_end': cursor_pos,
            'metadata': {}
        }
        self.log.info('returning', extra={'reply': reply})
        return reply

    def do_inspect(self, code, cursor_pos, detail_level=0, omit_sections=()):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#introspection
        # used by Jupyter lab's contextual help
        self.log.info('called with', extra=selfless(locals()))
        # identify the token under the cursor
        token = ''
        for m in self._re_tokens.finditer(code):
            if m.span()[1] >= cursor_pos:
                token = m.group().strip()
                if len(token) > 0:
                    break
        self.log.debug(f'getting help on token {repr(token)}')
        # get the result of `help` on the token
        help_text = None
        if len(token) > 0:
            try:
                help_text = self._matlab.help(token)
            except Exception as e:
                self.log.error('exception in Matlab engine', exc_info=e)
        # return the result of `help`
        if help_text is not None and len(help_text) > 0:
            reply = {
                'status': 'ok',
                'data': {'text/html':
                         f'<h1>Help for <code>{token}</code>'
                         + f'</h1>\n<pre>{help_text}</pre>'},
                'metadata': {},
                'found': True
                }
        else:
            reply = {
                'status': 'ok',
                'data': {},
                'metadata': {},
                'found': False
                }
        self.log.info('returning', extra={'reply': reply})
        return reply

    def do_history(self, hist_access_type, output, raw, session=None,
                   start=None, stop=None, n=None, pattern=None, unique=False):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#history

        # For this, we would need to read `History.xml` in the directory
        # returned by `prefdir`, read it with `xml.dom.minidom.parse`, and
        # aggregate commands from the different `<session>`s. At the end we
        # would have to add a `<session>` using the absurdly complicated DOM
        # interface, and write it back. Since the console has an integrated
        # per-session history, and the notebook retains commands anyway, I'm
        # not sure that's worth the hassle.
        #
        # Matlab itself does not separate properly between concurrent sessions.
        # It adds a new session when starting, but every new command is added
        # to the last session of the file, regardless of whether that is the
        # session which this instance created. It appears that the file is
        # reread and rewritten with every command. However, the active history
        # is not updated based on the reads.
        self.log.info('called with', extra=selfless(locals()))
        # do something
        reply = {
            'status': 'ok',
            'history': []
            }
        self.log.info('returning', extra={'reply': reply})
        return reply

    def do_is_complete(self, code):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#code-completeness
        # simple implementation absent a proper parser:
        # input is complete if its last line is empty
        self.log.info('called with', extra=selfless(locals()))
        if len(code.split('\n')[-1]) == 0:
            reply = {
                'status': 'complete'
                }
        else:
            reply = {
                'status': 'incomplete'
                }
        self.log.info('returning', extra={'reply': reply})
        return reply

    def do_shutdown(self, restart):
        # https://jupyter-client.readthedocs.io/en/latest/messaging.html#kernel-shutdown
        # `restart` is ignored
        self.log.info('called with', extra=selfless(locals()))
        self.log.info('stopping Matlab engine')
        try:
            self._matlab.quit()
        except Exception as e:
            self.log.error('exception in Matlab engine', exc_info=e)
        reply = {
            'status': 'ok',
            'restart': restart
            }
        self.log.info('returning', extra={'reply': reply})
        return reply


class StreamIO(StringIO):
    # used in `do_execute` to receive output (stdout / stderr),
    # directly from the Matlab engine's `eval` or intercepted by `pipes`,
    # postprocesses it, and send it on to the client

    _re_char_backspace = re.compile('[^\b\n]\b')

    def __init__(self, kernel, stream_name, silent):
        self._kernel = kernel
        self._stream_name = stream_name
        self._silent = silent

    def write(self, text):
        self._kernel.log.info('called with', extra=selfless(locals()))
        # process backspace
        n = 1
        while n > 0:
            text, n = self._re_char_backspace.subn('', text)
        # process carriage return
        text = text.replace('\r', '\n')
        # remove engine messages
        text = text.replace('Error using eval\n', '')
        text = text.replace('the MATLAB function has been cancelled\n', '')
        self._kernel.log.debug('processed', extra={'text': text})
        # send
        if (len(text) > 0) and not self._silent:
            self._kernel._send_text(self._stream_name, text)
