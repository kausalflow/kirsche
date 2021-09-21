## Tutorials

Some tutorials are provided here in this section.

## Install

```
pip install kirsche
```

??? warning "Install in an Environment"

    Unless you are using this in a temporary machine like a docker container, it is recommended to install this in an environment.

    For example, using conda, we can create an environment called `kirsche` or any other name you prefer,

    ```
    conda create -n "kirsche" python=3.7 pip
    ```

    then activate the environment

    ```
    conda activate kirsche
    ```

    Install kirsche in this environment

    ```
    pip install kirsche
    ```

### Visualizations

Suppose we have a bib file called `test.bib`, and we would like to generate an html file called `test.html`,

=== "Command"

    ```
    kirsche visualization -sb "test.bib" -th "test.html"
    ```

    Open the `test.html` file in your browser.

=== "Results"


    ![](assets/visualizations/visualization-demo-1.gif)


### Download metadata only

Using DOIs:

```
kirsche metadata -p "10.1016/j.sna.2020.112529" -p "10.1152/jn.00208.2014" -m save/to/file/path
```

Using a bib file:

```
kirsche metadata -b path/to/your/bib/file -m save/to/file/path
```


### Download and Calculate Connections

Using DOIs:

```
kirsche connections -p "10.1016/j.sna.2020.112529" -p "10.1152/jn.00208.2014" -c save/to/file/path
```

Using a bib file:

```
kirsche connections -b path/to/your/bib/file -c save/to/file/path
```
