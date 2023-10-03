import os
from typing import ClassVar

from openai import Embedding
import vecs
from vecs.collection import Numeric


# number of related job descriptions to return
QUERY_MAX: int = 5


def _setup_vector_store() -> vecs.Collection:
    _host = os.environ.get('RAW_SUPABASE_URL')
    _user = 'postgres'
    _password = os.environ.get('PG_PASS')
    _port = 5432
    _db_name = 'postgres'
    _url = f"postgresql://{_user}:{_password}@{_host}:{_port}/{_db_name}"
    vx = vecs.create_client(_url)
    return vx.get_or_create_collection(name="collection_test_1", dimension=1536)


class EmbeddingManager:
    _collection: ClassVar[vecs.Collection] = _setup_vector_store()

    def generate_embeddings(self, data: list[dict]):
        """ Generate embeddings for a batch of job descriptions.

        This should only need to be executed once to bootstrap the vector store.
        """
        embeddings = []

        for row in data:
            for key in ('id', 'desc'):
                assert key in row.keys()

            embed = self._embed(row['desc'])
            embeddings.append((row['id'],
                               embed,
                               {}))

        self._collection.upsert(records=embeddings)

    def query(self, text: str) -> list[str]:
        """ Get a list of related UUID's for rows related to given job description. """
        # TODO: use an adapter to convert str values to UUID4
        embedding = self._embed(text)

        # TODO: add embeddings to vector store
        return self._collection.query(
            data=embedding,
            limit=QUERY_MAX,
            include_value=False
        )

    @staticmethod
    def _embed(text: str) -> list[float]:
        response = Embedding.create(
            model="text-embedding-ada-002",
            input=[text]
        )
        return response["data"][0]["embedding"]

