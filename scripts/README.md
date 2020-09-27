Folder containing various scripts.

For more detail on how to run each script, please run :

```console
python scripts/<script_name> --help
```

## `save_graph.py`

A script that save the graph used in `prospector` as PNG file, so it can be inspected.

### Arguments

|    Name    | Type  | Default        | Description                                               |
|:----------:|-------|----------------|-----------------------------------------------------------|
| `tmp-file` | `str` | `/tmp/main.py` | Path for the temporary main file. Keep the default value. |
| `img`      | `str` | `./graph.pdf`  | Path of the image file where to save the graph.           |