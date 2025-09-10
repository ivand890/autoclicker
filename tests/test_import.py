def test_import_and_version():
    import autoclicker

    assert hasattr(autoclicker, "__version__")
    assert isinstance(autoclicker.__version__, str)
    assert len(autoclicker.__version__) > 0
