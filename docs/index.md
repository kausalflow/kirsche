# Documentation for Kirsche

Kirsche, connecting the papers.

> Kirsche is cherry in German.

Kirsche looks into the citations of the list of paper provided and establishes connections between each other. Kirsche can be used as a command line tool or in your python script.


## Install

```
pip install kirsche
```

This will leave out many dependencies. To install kirsche together with all the requirements,

```
pip install "kirsche[all]"
```

The extras options:

- `all`: everything
- `docs`: required to build the docs

## The Idea

The Kirsche command line tool provides a few functionalities:

1. Download the metadata of the given papers. Papers can be given as a list of doi or a bib file.
2. Calculate connections between the given papers.
3. Visualize the connections between the given papers.
