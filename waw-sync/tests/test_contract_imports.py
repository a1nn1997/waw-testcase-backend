def test_import_stubs():
    import identity_pb2  # noqa: F401
    import identity_pb2_grpc  # noqa: F401

    assert hasattr(identity_pb2, "UserProfile")
    assert hasattr(identity_pb2_grpc, "IdentityServiceStub")
