from knowledgeqa.embedding import FastEmbedEmbedder


class FakeBackend:
    def embed(self, texts, batch_size):
        assert batch_size == 64
        return [[float(len(text)), 1.0] for text in texts]


def test_fastembed_embedder_uses_injected_backend() -> None:
    embedder = FastEmbedEmbedder(backend=FakeBackend())

    vectors = embedder.embed(["abc", "de"])

    assert vectors == [[3.0, 1.0], [2.0, 1.0]]


def test_fastembed_embedder_reports_dimension() -> None:
    embedder = FastEmbedEmbedder(backend=FakeBackend())

    assert embedder.dimension() == 2
