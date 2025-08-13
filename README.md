# MKernel: A Jupyter Kernel for Matlab

MKernel is a Juypter kernel for Matlab, intended to be better in some respects than the existing options:

-   Calysto's [`matlab_kernel`](https://github.com/Calysto/matlab_kernel) has been around for a while, but unfortunately has been barely updated over the last years. Correspondingly, there are currently a lot of open issues which do not appear as if they will be fixed.

-   [`jupyter_matlab_kernel`](https://github.com/mathworks/jupyter-matlab-proxy/tree/main/src/jupyter_matlab_kernel) is a fairly new offering from The Mathworks itself, but unfortunately [it does not support](https://github.com/mathworks/jupyter-matlab-proxy/issues/48) [NBClient](https://nbclient.readthedocs.io/) and therefore neither [nbconvert](https://nbconvert.readthedocs.io/) nor [Quarto](https://quarto.org/), the latter being my primary interface to using Jupyter kernels.

I started to fix issues in a fork of `matlab_kernel`, but ultimately found it easier to start from scratch based on [*Making simple Python wrapper kernels*](https://jupyter-client.readthedocs.io/en/latest/wrapperkernels.html) and using [`echo_kernel`](https://github.com/jupyter/echo_kernel) as a template.

The kernel is implemented in Python 3. It was developed with Python 3.10 and Matlab R2023b (including matlabengine 23.2.1), and tested using Jupyter 5.3.1 (including notebook 6.5.5, lab 3.6.5, console 6.6.3, qtconsole 5.4.4), VSCode 1.83.0 (with the notebook and interactive window provided by the Jupyter extension v2023.9), and Quarto 1.4.388 (using NBClient 0.7.4), but later versions should work, too. Some features are only supported from Quarto 1.5 (see below).

If you use this software for academic work, I would appreciate a citation:

>   Allefeld, C. (2023). *MKernel: A Jupyter Kernel for Matlab* (1.2.0)

You can find the Zenodo DOI for this version from its GitHub release notes.


## Installation

I recommend to install the package into a virtual or Conda environment. The following instructions assume that such an environment has been activated and `pip` is available.

To install the `mkernel` package, run:
```bash
pip install git+https://github.com/allefeld/mkernel.git
```
This should also install the kernel for Jupyter.

MKernel derives its functionality from the The Mathworks' [Matlab Engine for Python](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html). The `mkernel` package lists `matlabengine` as a dependency and therefore pip will install it from PyPI automatically. However, newer versions of `matlabengine` drop support for earlier Matlab versions. It may therefore be necessary to install an [earlier version of `matlabengine`](https://pypi.org/project/matlabengine/#history) manually with:
```bash
pip install matlabengine==<version>
```
From Matlab R2023b, the matching `matlabengine` has a major version corresponding to the last two digits of the release year and a minor version of 1 or 2 for releases a and b, respectively, e.g. 23.2. For earlier versions: R2023a – 9.14, R2022b – 9.13, R2022a – 9.12, R2021b – 9.11, R2021a – 9.10, R2020b – 9.9.


## Usage

### Jupyter Notebook<br>JupyterLab<br>VS Code Jupyter Notebook<br>VS Code Interactive Console

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

The repository subdirectory [`examples/`](https://github.com/allefeld/mkernel/tree/main/examples) contains an example `qmd` file.

### Jupyter Console<br>Jupyter QtConsole

```bash
jupyter console --kernel mkernel
```
or
```bash
jupyter qtconsole --kernel mkernel
```

\
In the following, this documentation will refer to a notebook cell, executable code block, or other unit of code sent for execution as a 'code cell'.


## Functions and classes

If a code cell starts with `function` or `classdef`, the kernel attempts to identify the name of the function or class and writes the complete cell code to a file in the current directory, with that name and the extension `.m`.

Note that the file is written regardless of whether it already exists, which poses the danger of overwriting a different file with the same name. It is recommended to use a short prefix for all function and class names to prevent that.


## Configuration

MKernel configuration from Matlab is achieved by setting application data on the root element (`0` or `groot()`), which has no effect if the code is used outside of the kernel.

### Plot backend

```matlab
setappdata(0, "MKernel_plot_backend", backend)
```

The default backend is `"inline"`. With it, the kernel hides newly created figure windows, after each code cell execution writes them to files via Matlab's [`print` function](https://www.mathworks.com/help/matlab/ref/print.html), closes them, and displays the plots in the client.

With the backend `"native"`, figure windows appear as usual.

Mixing the two backends within the same session may lead to unexpected results.

### Plot format

```matlab
setappdata(0, "MKernel_plot_format", format)
```

The file format of plots displayed in the client by the `"inline"` backend, used as the `-d` argument to Matlab's `print` function; the initial value is `"png"`. All image formats supported by that function can be used:

| format(s)                              | mediatype                |
| -------------------------------------- | ------------------------ |
| `"png"`                                | `image/png`              |
| `"svg"`                                | `image/svg+xml`          |
| `"jpeg"`                               | `image/jpeg`             |
| `"tiff"`, `"tiffn"`                    | `image/tiff`             |
| `"meta"`                               | `application/emf`        |
| `"pdf"`                                | `application/pdf`        |
| `"eps"`, `"epsc"`, `"eps2"`, `"eps2c"` | `application/postscript` |

Note however that only `"png"`, `"svg"`, and `"jpeg"` can be expected to be displayed properly across clients. Moreover, Enhanced Metafiles (`"meta"`) are only supported on Windows.

From Quarto 1.5, the initial `MKernel_plot_format` is taken from the Quarto document option `fig-format` (`retina`, `png`, `jpeg`, `svg`, or `pdf`), with `retina` translated into `svg`. If not set explicitly, Quarto uses an output-format dependent default.

### Plot resolution

```matlab
setappdata(0, "MKernel_plot_resolution", resolution)
```

The resolution of plots displayed in the client by the `"inline"` backend, used as the `-r` argument to Matlab's `print` function. It is a number in dots per inch (dpi). The default is taken from the platform-dependent `"ScreenPixelsPerInch"` [root property](https://www.mathworks.com/help/matlab/ref/matlab.ui.root-properties.html).

The `-r` argument of `print` applies mainly to bitmap graphics formats, but depending on the renderer it may also apply to bitmap images embedded in vector graphics formats.

From Quarto 1.5, the initial `MKernel_plot_resolution` is taken from the Quarto document option `fig-dpi`. If not set explicitly, Quarto uses an output-format dependent default.

### Plot size

MKernel provides no special means to control the size of plots, because that can easily be achieved by Matlab code. For a figure with handle `fig` use code like:
```matlab
fig.PaperPosition(3:4) = [0, 0, width, height];
```
To set the default size for plots created subsequently, use:
```matlab
set(0, "defaultFigurePaperPosition", [0, 0, width, height])
set(0, "defaultFigurePaperPositionMode", "manual")
```

From Quarto 1.5, the initial `defaultFigurePaperPosition` is taken from the Quarto document options `fig-width` and `fig-height` (see [Figure size handling for Quarto](Figure_size_handling_for_Quarto.md) for more details). If not set explicitly, Quarto uses output-format dependent defaults.

### Output capture

```matlab
setappdata(0, "MKernel_output_capture", capture)
```

The kernel supports two ways to capture the standard output and standard error streams of executed Matlab code to send it to the client.

With `"wrapper"`, the Matlab engine is called in a [context](https://github.com/minrk/wurlitzer) in which all output is captured and sent to the client as it occurs, which means feedback is immediately available during code execution. Unfortunately, the Matlab engine has a [bug](https://github.com/mathworks/matlab-engine-for-python/issues/34) which garbles non-ASCII characters (starting from U+00A0 'no-break space') captured this way.

With `"engine"` the Matlab engine is asked to capture output itself, which provides proper Unicode support. The disadvantage is that the output only becomes available after each code execution (code cell) has finished.

The default setting is `"auto"`, which is equivalent to `"wrapper"` for interactive clients and equivalent to `"engine"` for non-interactive clients.

### Configuration of Matlab for MKernel

Before starting the Matlab engine, MKernel sets the environment variable `MKERNEL` to the kernel version. MKernel-specific initialization can therefore be performed in [`startup.m`](https://uk.mathworks.com/help/matlab/ref/startup.html) using an `if` block with condition `~isempty(getenv("MKERNEL"))`.


## GUI elements

Note that while the kernel runs Matlab in the background without the Desktop GUI, commands which bring up GUI elements are functional. For example:

-   `figure` and other graphics commands create *Figure* windows (though they are only visible with the `"native"` plot backend, see above).

-   `edit` opens a file in the *Editor* GUI element in a separate window, including functional debugging facilities.

-   `workspace` opens the *Workspace* GUI element in a separate window. If left open, interactive changes to workspace variables are reflected in its contents.

-   `doc` opens the *Help* GUI element in a separate window.

-   `profile report` opens the *Profiler* GUI element in a separate window. However, each pair of `profile on` and `profile off` commands should be within the same code cell, to avoid additional code run by the kernel to be included in the report.

-   `inputdlg` opens a GUI dialog and prompts the user for input.


## Limitations

-   Prompting the user for keyboard input within the client via the `input` function does not work.

-   Commands or output created by GUI elements (e.g. by running a file from the editor) do not appear in the client, though the commands are effective.

-   Tab completion is based on undocumented Matlab functionality and may therefore break (Java method `com.mathworks.jmi.MatlabMCR.mtFindAllTabCompletions`).

-   In Jupyter Console and similar interfaces which do not provide a special key (like <kbd>Shift+Enter</kbd>) to trigger execution, a code cell has to have an empty line at the end to be executed; otherwise a continuation line is prompted for.

-   Jupyter Console has a [bug](https://github.com/jupyter/jupyter_console/issues/296) which prevents code execution to be interrupted by <kbd>Ctrl+C</kbd>.

-   The `"wrapper"` method of output capture is not supported on Windows because of a [limitation](https://github.com/minrk/wurlitzer/issues/12) of the underlying `wurlitzer` package. The setting is silently ignored and the `"engine"` method used instead.

-   The configuration logic creates temporary Matlab variables with names of the form `MKernel_*`, which are later removed. If you use variables with names of this form, they will not persist between code cells.

A further intentional limitation is that MKernel does not implement IPython-style magics, because their use prevents using identical code in Matlab proper. However, most if not all of the interactive features which IPython adds to Python via magics (e.g. `%cd`, `%run`, `%edit`, `%logon`, `%system`, `%whos`, `!`) are already provided by Matlab.


## Cleanup

While editing a notebook and executing its cells, the kernel is not automatically restarted. Similary, by default Quarto [daemonizes](https://quarto.org/docs/advanced/jupyter/kernel-execution.html#daemonization) the kernel and re-uses it for reprocessing a document, e.g. if file changes are detected by `quarto preview`. As a consequence, the user cannot expect a clean Matlab environment in the first code cell. As a workaround, an initial code cell which cleans up Matlab, e.g.
```matlab
clear all
```
will be sufficient in most cases. For more thorough clean-up code, see [*How do I reset MATLAB to its launched state?*](https://www.mathworks.com/matlabcentral/answers/1093-how-do-i-reset-matlab-to-its-launched-state#answer_1535).

Function files written by the kernel are not automatically deleted; if desired, that can be achieved by `delete` commands in a final code cell.


## How to report issues

If you report an [issue](https://github.com/allefeld/mkernel/issues), please include a [minimal reproducible example](https://en.wikipedia.org/wiki/Minimal_reproducible_example), and attach the log file from running it. You can find the log file from the last kernel run with:

```bash
python3 -c "import os, tempfile, glob; print(glob.glob(os.path.join(tempfile.gettempdir(), 'mkernel-*'))[-1])"
```

***

This software is copyrighted © 2023–2024 by Carsten Allefeld and released under the terms of the GNU General Public License, version 3 or later.
