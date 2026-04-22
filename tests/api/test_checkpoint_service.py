from galgame_character_skills.api import checkpoint_service as svc
from galgame_character_skills.domain import TASK_TYPE_SUMMARIZE


class DummyCheckpointGateway:
    def __init__(self):
        self._ckpt = {"checkpoint_id": "c1", "task_type": TASK_TYPE_SUMMARIZE, "input_params": {"role_name": "r"}}
        self._llm_state = {"messages": []}
        self.deleted = False

    def list_checkpoints(self, task_type=None, status=None):
        return [{"checkpoint_id": "c1", "task_type": task_type, "status": status}]

    def load_checkpoint(self, checkpoint_id):
        if checkpoint_id == "missing":
            return None
        return dict(self._ckpt, checkpoint_id=checkpoint_id)

    def load_llm_state(self, checkpoint_id):
        return self._llm_state

    def delete_checkpoint(self, checkpoint_id):
        if checkpoint_id == "missing":
            return False
        self.deleted = True
        return True


def test_list_checkpoints_result():
    gw = DummyCheckpointGateway()

    listed = svc.list_checkpoints_result(gw, task_type=TASK_TYPE_SUMMARIZE, status="failed")
    assert listed["success"] is True
    assert listed["checkpoints"][0]["task_type"] == TASK_TYPE_SUMMARIZE


def test_get_checkpoint_result_success():
    gw = DummyCheckpointGateway()
    got = svc.get_checkpoint_result(gw, "c1")
    assert got["success"] is True
    assert got["checkpoint"]["checkpoint_id"] == "c1"


def test_get_checkpoint_result_missing():
    gw = DummyCheckpointGateway()
    missing = svc.get_checkpoint_result(gw, "missing")
    assert missing["success"] is False


def test_delete_checkpoint_result_success():
    gw = DummyCheckpointGateway()
    deleted = svc.delete_checkpoint_result(gw, "c1")
    assert deleted["success"] is True


def test_delete_checkpoint_result_missing():
    gw = DummyCheckpointGateway()
    del_missing = svc.delete_checkpoint_result(gw, "missing")
    assert del_missing["success"] is False
