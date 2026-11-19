"""Unit tests for bounded PostgreSQL connection reuse."""
import unittest
from unittest.mock import MagicMock, patch

from tracker.repositories import postgres_connection_pool as pool_module


class PostgreSQLConnectionPoolTests(unittest.TestCase):
    def setUp(self):
        pool_module.close_all_pools()

    def tearDown(self):
        pool_module.close_all_pools()

    def test_reuses_one_pool_and_returns_connections_without_closing_them(self):
        raw_connection = MagicMock()
        transaction = MagicMock()
        transaction.__enter__.return_value = None
        transaction.__exit__.return_value = False
        raw_connection.transaction.return_value = transaction
        pool = MagicMock()
        pool.getconn.return_value = raw_connection

        with patch.object(
            pool_module, "ConnectionPool", return_value=pool
        ) as pool_factory:
            first = pool_module.get_pooled_connection(
                "postgresql://example.invalid/database",
                connect_timeout=3,
                sslmode="require",
                store="growth_history",
            )
            with first as connection:
                connection.execute("SELECT 1")
            first.close()
            first.close()

            second = pool_module.get_pooled_connection(
                "postgresql://example.invalid/database",
                connect_timeout=3,
                sslmode="require",
                store="growth_history",
            )
            second.close()

        pool_factory.assert_called_once()
        self.assertEqual(pool.getconn.call_count, 2)
        self.assertEqual(pool.putconn.call_count, 2)
        raw_connection.close.assert_not_called()
        self.assertEqual(transaction.__enter__.call_count, 1)
        self.assertEqual(transaction.__exit__.call_count, 1)
        self.assertEqual(
            pool_factory.call_args.kwargs["max_size"],
            pool_module._POOL_MAX_SIZE,
        )

    def test_different_connection_options_use_separate_pools(self):
        first_pool = MagicMock()
        second_pool = MagicMock()
        first_pool.getconn.return_value = MagicMock()
        second_pool.getconn.return_value = MagicMock()

        with patch.object(
            pool_module,
            "ConnectionPool",
            side_effect=[first_pool, second_pool],
        ) as pool_factory:
            first = pool_module.get_pooled_connection(
                "postgresql://example.invalid/database",
                sslmode="require",
            )
            first.close()
            second = pool_module.get_pooled_connection(
                "postgresql://example.invalid/database",
                sslmode="disable",
            )
            second.close()

        self.assertEqual(pool_factory.call_count, 2)

    def test_transaction_rolls_back_when_repository_operation_fails(self):
        raw_connection = MagicMock()
        transaction = MagicMock()
        transaction.__enter__.return_value = None
        transaction.__exit__.return_value = False
        raw_connection.transaction.return_value = transaction
        pool = MagicMock()
        pool.getconn.return_value = raw_connection

        with patch.object(pool_module, "ConnectionPool", return_value=pool):
            connection = pool_module.get_pooled_connection(
                "postgresql://example.invalid/database"
            )
            with self.assertRaisesRegex(ValueError, "write failed"):
                with connection:
                    raise ValueError("write failed")
            connection.close()

        transaction.__exit__.assert_called_once()
        self.assertIs(transaction.__exit__.call_args.args[0], ValueError)
        pool.putconn.assert_called_once_with(raw_connection)


if __name__ == "__main__":
    unittest.main()
