from scaffold.professional.esco_importer import (
    COLLECTION_MAP,
    csv_to_entity_type,
    map_occ_skill_relation_type,
    map_skill_skill_relation_type,
)
from scaffold.professional.cbo_importer import (
    clean_label,
    make_cbo_external_id,
    profile_activity_relation_type,
    profile_area_relation_type,
)
from scaffold.professional.normalization import deduplicate_normalized, normalize_text, split_alias_field


def test_normalize_text_lowercases_and_trims():
    assert normalize_text("  Python  ") == "python"


def test_normalize_text_collapses_internal_spaces():
    assert normalize_text("big  data") == "big data"


def test_normalize_text_preserves_accents():
    assert normalize_text("Análise de Dados") == "análise de dados"


def test_normalize_text_empty_string():
    assert normalize_text("") == ""


def test_split_alias_field_by_pipe():
    assert split_alias_field("foo|bar|baz") == ["foo", "bar", "baz"]


def test_split_alias_field_by_newline():
    assert split_alias_field("foo\nbar") == ["foo", "bar"]


def test_split_alias_field_mixed_separators():
    assert split_alias_field("foo\nbar|baz") == ["foo", "bar", "baz"]


def test_split_alias_field_ignores_empty_segments():
    assert split_alias_field("foo||") == ["foo"]


def test_split_alias_field_strips_whitespace():
    assert split_alias_field("  foo  |  bar  ") == ["foo", "bar"]


def test_deduplicate_normalized_removes_case_duplicates():
    result = deduplicate_normalized(["Python", "python", "PYTHON"])
    assert len(result) == 1
    assert result[0] == "Python"


def test_deduplicate_normalized_preserves_order():
    result = deduplicate_normalized(["Banana", "Apple", "banana"])
    assert result == ["Banana", "Apple"]


def test_deduplicate_normalized_ignores_empty_strings():
    result = deduplicate_normalized(["foo", "", "  "])
    assert result == ["foo"]


def test_skill_csv_maps_to_skill_entity_type():
    assert csv_to_entity_type("skills_pt.csv") == "skill"


def test_occupation_csv_maps_to_occupation():
    assert csv_to_entity_type("occupations_pt.csv") == "occupation"


def test_skill_groups_csv_maps_to_domain():
    assert csv_to_entity_type("skillGroups_pt.csv") == "domain"


def test_isco_groups_csv_maps_to_domain():
    assert csv_to_entity_type("ISCOGroups_pt.csv") == "domain"


def test_collection_map_contains_all_seven_slugs():
    expected = {
        "digital_skills",
        "digcomp_skills",
        "green_skills",
        "language_skills",
        "research_skills",
        "transversal_skills",
        "research_occupations",
    }
    assert set(COLLECTION_MAP.keys()) == expected


def test_occ_skill_relation_essential_maps_correctly():
    assert map_occ_skill_relation_type("essential") == "essential_skill"


def test_occ_skill_relation_optional_maps_correctly():
    assert map_occ_skill_relation_type("optional") == "optional_skill"


def test_occ_skill_relation_unknown_falls_back_to_optional():
    assert map_occ_skill_relation_type("unknown") == "optional_skill"


def test_skill_skill_relation_essential_maps_correctly():
    assert map_skill_skill_relation_type("essential") == "essential_related_skill"


def test_skill_skill_relation_optional_maps_correctly():
    assert map_skill_skill_relation_type("optional") == "optional_related_skill"


def test_clean_label_collapses_whitespace_preserving_case():
    assert clean_label("  ENGENHEIRO   DE   SOFTWARE  ") == "ENGENHEIRO DE SOFTWARE"


def test_make_cbo_external_id_for_coded_levels_is_readable():
    assert make_cbo_external_id("ocupacao", "251510") == "ocupacao:251510"


def test_make_cbo_external_id_for_activity_is_stable_hash():
    first = make_cbo_external_id("atividade", "Trabalhar em equipe")
    second = make_cbo_external_id("atividade", "  Trabalhar   em equipe ")
    assert first == second
    assert first.startswith("atividade:")


def test_cbo_profile_area_relation_type_is_canonical():
    assert profile_area_relation_type() == "cbo_area"


def test_cbo_profile_activity_relation_type_is_canonical():
    assert profile_activity_relation_type() == "cbo_activity"
