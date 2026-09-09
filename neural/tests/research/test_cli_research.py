import pytest

from src.cli.research import build_parser, main


def test_all_stages_have_required_bindings():
    parser = build_parser()
    for stage in ('audit','prepare','me-export','me-import','train','calibrate','templates','freeze','infer','report'):
        args = parser.parse_args([stage,'--dataset','atlas2020_4lep','--protocol','protocol.json','--run-dir','runs/new'])
        assert args.command == stage
        with pytest.raises(SystemExit):
            parser.parse_args([stage,'--run-dir','runs/new'])


def test_bad_protocol_is_input_error_without_starting_run(tmp_path):
    assert main(['audit','--dataset','atlas2020_4lep','--protocol',str(tmp_path/'missing'),
                 '--run-dir',str(tmp_path/'run')]) == 3
    assert not (tmp_path/'run').exists()
