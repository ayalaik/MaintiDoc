from llama_index.core import SimpleDirectoryReader

docs = SimpleDirectoryReader("corpus", recursive=True, required_exts=[".pdf"]).load_data()

for d in docs:
    print(d.metadata.get("file_name"), "| page", d.metadata.get("page_label"),
          "| longueur:", len(d.text), "| NUL:", d.text.count("\x00"))