from galgame_character_skills.gateways.executor_gateway import DefaultExecutorGateway


def test_executor_gateway_creates_usable_pool():
    gateway = DefaultExecutorGateway()
    executor = gateway.create(max_workers=2)
    try:
        future = executor.submit(lambda x: x + 1, 1)
        assert future.result() == 2
    finally:
        executor.shutdown(wait=True)
