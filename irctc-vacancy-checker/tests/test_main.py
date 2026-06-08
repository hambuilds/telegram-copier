"""Tests for CLI main module."""

import pytest
from main import build_parser


def test_parser_required_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_valid_args():
    parser = build_parser()
    args = parser.parse_args(["--train", "12601", "--from", "CLT", "--to", "MAS", "--class", "SL", "--date", "2026-06-09"])
    assert args.train == "12601"
    assert args.origin == "CLT"
    assert args.destination == "MAS"
    assert args.class_type == "SL"
    assert args.date == "2026-06-09"
    assert args.headless is True