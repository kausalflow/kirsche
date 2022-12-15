# Use in Code

The command line tool covers most of the use cases. If more customizations is desired, please refer to [References](../references/index.md) for details about the utilities.

## An Example

```python
from kirsche.download import download_metadata
from kirsche.connect import (
    append_connections,
    save_connected_papers,
)

paper_ids = ["10.1523/JNEUROSCI.0095-07.2007"]

# download the metadata
papers_metadata = download_metadata(paper_ids)

# calculate the connections
papers_connections = append_connections(papers_metadata)

# save the connections to a file, e.g., save_paper_connections.json
save_connected_papers(papers_connections, target="save_paper_connections.json")
```

!!! note "Loading from a bib file"

    If we have a bib file `my_input_bib_file.bib`, we can extract the ids using [`list_unique_ids`][kirsche.download.list_unique_ids]

    ```python
    from kirsche.download import list_unique_ids

    paper_ids = list_unique_ids("my_input_bib_file.bib")
    ```
