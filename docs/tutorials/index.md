## Tutorials

Some tutorials are provided here in this section.

### Download metadata only

Using DOIs:

```python
kirsche metadata -p "10.1016/j.sna.2020.112529" -p "10.1152/jn.00208.2014" -m save/to/file/path
```

Using a bib file:

```python
kirsche metadata -b path/to/your/bib/file -m save/to/file/path
```


### Download and Calculate Connections

Using DOIs:

```python
kirsche connections -p "10.1016/j.sna.2020.112529" -p "10.1152/jn.00208.2014" -c save/to/file/path
```

Using a bib file:

```python
kirsche connections -b path/to/your/bib/file -c save/to/file/path
```
