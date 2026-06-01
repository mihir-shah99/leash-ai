import sys
import os

# Ensure apps/api is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.policy.translator import CedarPolicyTranslator

def test_translate_block_tool():
    res = CedarPolicyTranslator.translate("Block agents from using execute_sql")
    assert res["success"] is True
    assert 'context.tool_name == "execute_sql"' in res["cedar_content"]
    assert "forbid" in res["cedar_content"]

def test_translate_numeric_greater():
    res = CedarPolicyTranslator.translate("Block issue_refund when amount is greater than 500")
    assert res["success"] is True
    assert 'context.tool_name == "issue_refund"' in res["cedar_content"]
    assert 'context.amount > 500' in res["cedar_content"]

def test_translate_numeric_less():
    res = CedarPolicyTranslator.translate("Forbid issue_refund if amount is less than 100")
    assert res["success"] is True
    assert 'context.tool_name == "issue_refund"' in res["cedar_content"]
    assert 'context.amount < 100' in res["cedar_content"]

def test_translate_text_contains():
    res = CedarPolicyTranslator.translate("Block execute_sql when query contains drop table")
    assert res["success"] is True
    assert 'context.tool_name == "execute_sql"' in res["cedar_content"]
    assert '"drop table" in context.query' in res["cedar_content"]

def test_translate_global_contains():
    res = CedarPolicyTranslator.translate("Block queries containing rm -rf")
    assert res["success"] is True
    assert '"rm -rf" in context.query' in res["cedar_content"]
