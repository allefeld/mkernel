# MKernel: A Jupyter Kernel for Matlab

MKernel is a Juypter kernel for Matlab, intended to be better in some respects than the existing options:

-   Calysto's [`matlab_kernel`](https://github.com/Calysto/matlab_kernel) has been around for a while, but unfortunately has been barely updated over the last years. Correspondingly, there are currently a lot of open issues which do not appear as if they will be fixed.

-   [`jupyter_matlab_kernel`](https://github.com/mathworks/jupyter-matlab-proxy/tree/main/src/jupyter_matlab_kernel) is a fairly new offering from The Mathworks itself, but unfortunately [it does not support](https://github.com/mathworks/jupyter-matlab-proxy/issues/48) [NBClient](https://nbclient.readthedocs.io/) and therefore neither [nbconvert](https://nbconvert.readthedocs.io/) nor [Quarto](https://quarto.org/), the latter being my primary interface to using Jupyter kernels.

I started to fix issues in a fork of `matlab_kernel`, but ultimately found it easier to start from scratch based on [*Making simple Python wrapper kernels*](https://jupyter-client.readthedocs.io/en/latest/wrapperkernels.html) and using [`echo_kernel`](https://github.com/jupyter/echo_kernel) as a template.

The kernel is implemented in Python 3. It was developed with Python 3.10 and Matlab R2023b (including matlabengine 23.2.1), and tested using Jupyter 5.3.1 (including notebook 6.5.5, lab 3.6.5, console 6.6.3, qtconsole 5.4.4), VSCode 1.83.0 (with the notebook and interactive window provided by the Jupyter extension v2023.9), and Quarto 1.4.388 (using NBClient 0.7.4).

If you use this software for academic work, I would appreciate a citation:

>   Allefeld, C. (2023). *MKernel: A Jupyter Kernel for Matlab* (1.0.0)

You can find the Zenodo DOI for this version from its GitHub release notes.


## Installation

I recommend that you install the package into a virtual or Conda environment. The following instructions assume that such an environment has been activated and `pip` is available.

To install the `mkernel` package, run:
```bash
pip install git+https://github.com/allefeld/mkernel.git
```
This should also install the kernel for Jupyter.

MKernel derives its functionality from the The Mathworks' [Matlab Engine for Python](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html). The `mkernel` package lists `matlabengine` as a dependency and therefore pip will install it from PyPI automatically. However, newer versions of `matlabengine` drop support for earlier Matlab versions. You may therefore have to install an [earlier version of `matlabengine`](https://pypi.org/project/matlabengine/#history) manually with:
```bash
pip install matlabengine==<version>
```
A partial compatibility list is R2023b: 23.2, R2023a: 9.14, R2022b: 9.13, R2022a: 9.12, R2021b: 9.11, R2021a: 9.10, R2020b: 9.9.


## Usage

### Jupyter Notebook & JupyterLab and VS Code Jupyter Notebook & Interactive Console

Select *MKernel* as the kernel.

The repository subdirectory [`examples/`](https://github.com/allefeld/mkernel/tree/main/examples) contains an example notebook.

### Quarto

In the metadata, include:
```yaml
jupyter: mkernel
```

Then use executable code blocks with language `matlab`:
````markdown
```{matlab}
cos(pi)
```
````

By default, Quarto daemonizes the kernel and re-uses it for reprocessing a document, e.g. if file changes are detected by `quarto preview`. This speeds up processing, but has the side effect that the user cannot expect a clean Matlab environment in the first code cell. To disable this behavior, you can add

```yaml
execute:
  daemon: false
```

to the metadata, but at the price of longer processing times. Instead, in most cases it will be sufficient to use an initial hidden code cell which cleans up Matlab:

````markdown
```{matlab}
%| echo: false
clear all
```
````

For more thorough clean-up code, see [*How do I reset MATLAB to its launched state?*](https://www.mathworks.com/matlabcentral/answers/1093-how-do-i-reset-matlab-to-its-launched-state#answer_1535).

The repository subdirectory [`examples/`](https://github.com/allefeld/mkernel/tree/main/examples) contains an example `qmd` file.

### Jupyter Console & Jupyter QtConsole

Start with the option `--kernel mkernel`.


## GUI elements

Note that while the kernel runs Matlab in the background without the Desktop GUI, commands which bring up GUI elements are functional. For example:

-   `figure` and other graphics commands create *Figure* windows (though they are only visible with the `"native"` plot backend, see below).

-   `edit` opens a file in the *Editor* GUI element in a separate window, including functional debugging facilities.

-   `workspace` opens the *Workspace* GUI element in a separate window. If you leave it open, interactive changes to workspace variables are reflected in its contents.

-   `doc` opens the *Help* GUI element in a separate window.

-   `profile report` opens the *Profiler* GUI element in a separate window. However, ensure that you use `profile on` and `profile off` within the same code execution (notebook cell) to avoid additional code run by the kernel to be included in the report.

-   `inputdlg` opens a GUI dialog and prompts the user for input.


## Configuration

MKernel does not implement magics, because their use prevents using identical code in Matlab proper, and because most if not all of the interactive features which IPython adds to Python via magics (e.g. `%cd`, `%run`, `%edit`, `%logon`, `%system`, `%whos`, `!`) are already provided by Matlab.

MKernel configuration from Matlab is achieved by setting application data on the root element (`0` or `groot`), which has no effect if the code is used outside of the kernel.

### Plot backend

```matlab
setappdata(0, "MKernel_plot_backend", backend)
```

The default backend is `"inline"`. With it, the kernel hides newly created figure windows, and after each code execution (notebook cell) writes them to files via Matlab's [`print` function](https://www.mathworks.com/help/matlab/ref/print.html), closes them, and displays the plots in the client.

With the backend `"native"`, the kernel does not intervene in normal Matlab operation, and figure windows appear as usual.

Mixing the two frontends within the same session may lead to unexpected results.

### Plot format

```matlab
setappdata(0, "MKernel_plot_format", format)
```

The file format of plots displayed in the client by the `"inline"` backend, used as the `-d` argument to Matlab's `print` function; the default is `"png"`. All image formats supported by that function can be used. They are, along with the used mediatype:

```
"png"                             image/png
"svg"                             image/svg+xml
"jpeg"                            image/jpeg
"tiff", "tiffn"                   image/tiff
"meta"                            application/emf
"pdf"                             application/pdf
"eps", "epsc", "eps2", "eps2c"    application/postscript
```

Note however that only `"png"`, `"svg"`, and `"jpeg"` can be expected to be displayed properly across clients. Moreover, Enhanced Metafiles (`"meta"`) are only supported on Windows.

### Plot resolution

```matlab
setappdata(0, "MKernel_plot_resolution", resolution)
```

The resolution of plots displayed in the client by the `"inline"` backend, used as the `-r` argument to Matlab's `print` function. It is a number in dots per inch (dpi). The default is taken from the platform-dependent `"ScreenPixelsPerInch"` [root property](https://www.mathworks.com/help/matlab/ref/matlab.ui.root-properties.html).

The `-r` argument of `print` applies mainly to bitmap graphics formats, but depending on the renderer it may also apply to bitmap images embedded in vector graphics formats.

### Plot size

MKernel provides no special means to control the size of plots, because that can easily be achieved by Matlab code. For a figure with handle `fig` use code like:
```matlab
pos = fig.Position;
pos(3:4) = [width, height];
fig.Position = pos;
```
To set the default size for plots created subsequently, use:
```matlab
pos = get(0, "defaultFigurePosition");
pos(3:4) = [width, height];
set(0, "defaultFigurePosition", pos)
```

### Output capture

```matlab
setappdata(0, "MKernel_output_capture", capture)
```

The kernel supports two ways to capture the standard output and standard error streams of executed Matlab code to send it to the client.

With `"wrapper"`, the Matlab engine is called in a [context](https://github.com/minrk/wurlitzer) in which all output is captured and sent to the client as it occurs, which means feedback is immediately available during each code execution (notebook cell). Unfortunately, the Matlab engine has a [bug](https://github.com/mathworks/matlab-engine-for-python/issues/34) which garbles non-ASCII characters (starting from U+00A0 'no-break space') captured this way.

With `"engine"` the Matlab engine is asked to capture output itself, which provides proper Unicode support. The disadvantage is that the output only becomes available after each code execution (notebook cell) has finished.

The default setting is `"auto"`, which is equivalent to `"wrapper"` for interactive clients and equivalent to `"engine"` for non-interactive clients.

### Configuration of Matlab for MKernel

Before starting the Matlab engine, MKernel sets the environment variable `MKERNEL` to the kernel version. MKernel-specific initialization can therefore be performed in [`startup.m`](https://uk.mathworks.com/help/matlab/ref/startup.html) using an `if` block with condition `~isempty(getenv("MKERNEL"))`.


## Limitations

-   Prompting the user for keyboard input within the client via the `input` function does not work.

-   Commands or output created by GUI elements opened in separate windows do not appear in the client, though the commands are effective.

-   Tab completion is based on undocumented Matlab functionality and may therefore break (Java method `com.mathworks.jmi.MatlabMCR.mtFindAllTabCompletions`).

-   In Jupyter Console and similar interfaces which do not provide a special key (like <kbd>Shift+Enter</kbd>) to trigger execution, the input has to have an empty line at the end to be executed; otherwise a continuation line is prompted for.

-   Jupyter Console has a [bug](https://github.com/jupyter/jupyter_console/issues/296) which prevents code execution to be interrupted by <kbd>Ctrl+C</kbd>.

-   The configuration logic creates temporary Matlab variables with names of the form `MKernel_*`, which are later removed. If you use variables with names of this form, they will not be retained between code executions (notebook cells).


## How to report issues

If you report an [issue](https://github.com/allefeld/mkernel/issues), please include a [minimal reproducible example](https://en.wikipedia.org/wiki/Minimal_reproducible_example), and attach the log file from running it. You can find the log file from the last kernel run with:

```bash
python3 -c "import os, tempfile, glob; print(glob.glob(os.path.join(tempfile.gettempdir(), 'mkernel-*'))[-1])"
```

***

This software is copyrighted © 2023 by Carsten Allefeld and released under the terms of the GNU General Public License, version 3 or later.
