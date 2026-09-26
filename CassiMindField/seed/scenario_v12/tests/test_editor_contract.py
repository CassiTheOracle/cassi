import runpy


editor = runpy.run_path("src/source_editor.py")
assert callable(editor["apply_patch_set"])
assert callable(editor["propose_candidates"])
