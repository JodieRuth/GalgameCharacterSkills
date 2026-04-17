import pytest

import galgame_character_skills.gateways as gateways


def test_gateways_lazy_export_resolves_known_symbol():
    cls = gateways.DefaultVndbGateway
    assert cls.__name__ == "DefaultVndbGateway"


def test_gateways_lazy_export_rejects_unknown_symbol():
    with pytest.raises(AttributeError):
        _ = gateways.NotExistingGateway
