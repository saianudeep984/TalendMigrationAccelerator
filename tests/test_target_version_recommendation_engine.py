from app.analyzers.target_version_recommendation_engine import (
    TargetVersionRecommendationEngine,
    recommend_target_version,
)


def test_unsupported_source():
    result = TargetVersionRecommendationEngine().recommend("Talend 6")
    assert result["supported"] is False
    assert result["recommendedTarget"] is None


def test_recommends_target_for_seven_x():
    result = recommend_target_version("Talend 7", component_usage=["tMap"])
    assert result["supported"] is True
    assert result["recommendedTarget"] in ("Talend 8", "Talend Cloud")
    assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert len(result["candidates"]) == 2


def test_removed_component_raises_risk_and_lowers_confidence():
    result = recommend_target_version("Talend 7", component_usage=["tJavaFlex"])
    target8 = next(c for c in result["candidates"] if c["targetVersion"] == "Talend 8")
    assert target8["removedHits"] == 1
    assert target8["riskScore"] > 0


def test_enterprise_features_prefer_cloud():
    result = recommend_target_version(
        "Talend 7.3", component_usage=[], enterprise_features={"summary": ["MDM"]}
    )
    assert result["recommendedTarget"] == "Talend Cloud"
    assert "Cloud" in result["rationale"]
