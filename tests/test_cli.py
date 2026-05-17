"""
Tests for CLI commands.

Tests all env-doctor CLI commands to ensure they work correctly.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from env_doctor.main import app

runner = CliRunner()


class TestMainApp:
    """Test main application."""
    
    def test_version(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "env-doctor version:" in result.stdout
    
    def test_help(self):
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "env-doctor" in result.stdout
        assert "Runtime compatibility intelligence" in result.stdout


class TestUpdateCommand:
    """Test update-db command."""
    
    @patch('env_doctor.cli.update.YAMLCompiler')
    @patch('env_doctor.cli.update.DatabaseManager')
    def test_update_db_success(self, mock_db, mock_compiler):
        """Test successful database update."""
        # Mock compiler to return success stats
        mock_compiler_instance = Mock()
        mock_compiler_instance.compile_all.return_value = {
            'files_fetched': 3,
            'rules_processed': 10,
            'stacks_processed': 5,
            'profiles_processed': 3,
            'errors': 0
        }
        mock_compiler.return_value = mock_compiler_instance
        
        result = runner.invoke(app, ["update-db"])
        
        # Should succeed
        assert result.exit_code == 0
        assert "Database updated successfully" in result.stdout or "Update" in result.stdout
    
    def test_update_db_help(self):
        """Test update-db --help."""
        result = runner.invoke(app, ["update-db", "--help"])
        assert result.exit_code == 0
        assert "Update local database" in result.stdout


class TestInspectCommand:
    """Test inspect command."""
    
    @patch('env_doctor.cli.inspect.get_python_version')
    @patch('env_doctor.cli.inspect.get_cuda_version')
    @patch('env_doctor.cli.inspect.get_gpu_info')
    @patch('env_doctor.cli.inspect.get_platform_info')
    @patch('env_doctor.cli.inspect.get_installed_packages')
    def test_inspect_table_format(self, mock_packages, mock_platform, mock_gpu, mock_cuda, mock_python):
        """Test inspect with table format."""
        # Mock environment info
        mock_python.return_value = "3.10.5"
        mock_cuda.return_value = "12.1"
        mock_gpu.return_value = {
            'count': 1,
            'gpus': [{'name': 'RTX 3090', 'memory_total': '24GB', 'driver_version': '535.104'}]
        }
        mock_platform.return_value = {
            'system': 'Linux',
            'release': '5.15.0',
            'machine': 'x86_64',
            'processor': 'x86_64'
        }
        mock_packages.return_value = [
            {'name': 'numpy', 'version': '1.24.3'},
            {'name': 'torch', 'version': '2.0.1'}
        ]
        
        result = runner.invoke(app, ["inspect", "--no-packages"])
        
        assert result.exit_code == 0
        assert "3.10.5" in result.stdout
    
    @patch('env_doctor.cli.inspect.get_full_environment_info')
    def test_inspect_json_format(self, mock_env):
        """Test inspect with JSON format."""
        mock_env.return_value = {
            'python_version': '3.10.5',
            'cuda_version': '12.1',
            'gpu_info': None,
            'platform': {'system': 'Linux'},
            'packages': []
        }
        
        result = runner.invoke(app, ["inspect", "--format", "json", "--no-packages"])
        
        assert result.exit_code == 0
        # Should output valid JSON (skip the "Scanning environment..." line)
        try:
            # Find the JSON part (starts with '{')
            json_start = result.stdout.find('{')
            if json_start != -1:
                json_output = result.stdout[json_start:].strip()
                json.loads(json_output)
            else:
                pytest.fail("No JSON found in output")
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    def test_inspect_help(self):
        """Test inspect --help."""
        result = runner.invoke(app, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "Scan and display" in result.stdout


class TestCheckCommand:
    """Test check command."""
    
    def test_check_missing_file(self):
        """Test check with non-existent file."""
        result = runner.invoke(app, ["check", "nonexistent.txt"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
    
    def test_check_help(self):
        """Test check --help."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "Check compatibility" in result.stdout


class TestRecommendCommand:
    """Test recommend command."""
    
    @patch('env_doctor.cli.recommend.get_python_version')
    @patch('env_doctor.cli.recommend.get_cuda_version')
    @patch('env_doctor.cli.recommend.DatabaseManager')
    def test_recommend_basic(self, mock_db, mock_cuda, mock_python):
        """Test basic recommend command."""
        mock_python.return_value = "3.10.5"
        mock_cuda.return_value = None
        
        # Mock database to return no stacks
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        result = runner.invoke(app, ["recommend", "--no-interactive"])
        
        # Should run without crashing
        assert result.exit_code in [0, 1]  # 0 if stacks found, 1 if not
    
    def test_recommend_help(self):
        """Test recommend --help."""
        result = runner.invoke(app, ["recommend", "--help"])
        assert result.exit_code == 0
        assert "Recommend stable package stack" in result.stdout


class TestVRAMCommand:
    """Test vram command."""
    
    @patch('env_doctor.cli.vram.ModelFetcher')
    def test_vram_estimation(self, mock_fetcher):
        """Test VRAM estimation."""
        # Mock model architecture
        mock_arch = Mock()
        mock_arch.model_id = "gpt2"
        mock_arch.model_type = "gpt2"
        mock_arch.param_count = 124000000
        mock_arch.hidden_size = 768
        mock_arch.num_layers = 12
        mock_arch.vocab_size = 50257
        mock_arch.num_heads = 12
        mock_arch.intermediate_size = 3072
        
        mock_fetcher_instance = mock_fetcher.return_value
        mock_fetcher_instance.fetch_model_info.return_value = mock_arch
        mock_fetcher_instance.fetch_model_info_from_file.return_value = None

        result = runner.invoke(app, ["vram", "--model", "gpt2"])
        
        assert result.exit_code == 0
        assert "VRAM" in result.stdout or "Estimating" in result.stdout
    
    @patch('env_doctor.cli.vram.ModelFetcher')
    def test_vram_with_quantization(self, mock_fetcher):
        """Test VRAM estimation with quantization."""
        mock_arch = Mock()
        mock_arch.model_id = "gpt2"
        mock_arch.param_count = 124000000
        mock_arch.num_layers = 12
        mock_arch.vocab_size = 50257
        mock_arch.hidden_size = 768
        mock_arch.model_type = "gpt2"
        
        mock_fetcher_instance = mock_fetcher.return_value
        mock_fetcher_instance.fetch_model_info.return_value = mock_arch
        mock_fetcher_instance.fetch_model_info_from_file.return_value = None

        result = runner.invoke(app, ["vram", "--model", "gpt2", "--quant", "int8"])
        
        assert result.exit_code == 0
    
    def test_vram_help(self):
        """Test vram --help."""
        result = runner.invoke(app, ["vram", "--help"])
        assert result.exit_code == 0
        assert "Estimate VRAM" in result.stdout


class TestPatchCommand:
    """Test patch command."""
    
    def test_patch_missing_file(self):
        """Test patch with non-existent file."""
        result = runner.invoke(app, ["patch", "nonexistent.txt"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
    
    def test_patch_dry_run(self):
        """Test patch in dry-run mode."""
        # Create temporary requirements file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("numpy>=1.20.0\n")
            f.write("torch>=2.0.0\n")
            temp_file = f.name
        
        try:
            result = runner.invoke(app, ["patch", temp_file, "--dry-run"])
            
            # Should run without errors
            assert result.exit_code in [0, 1]
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def test_patch_help(self):
        """Test patch --help."""
        result = runner.invoke(app, ["patch", "--help"])
        assert result.exit_code == 0
        assert "Detect and fix incompatibilities" in result.stdout


class TestReportCommand:
    """Test report-incompatibility command."""
    
    def test_report_missing_file(self):
        """Test report with non-existent file."""
        result = runner.invoke(app, ["report-incompatibility", "nonexistent.py"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
    
    def test_report_successful_script(self):
        """Test report with successful script."""
        # Create temporary Python script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('Hello, World!')\n")
            temp_file = f.name
        
        try:
            result = runner.invoke(app, ["report-incompatibility", temp_file, "--no-submit"])
            
            # Should succeed
            assert result.exit_code == 0
            assert "successfully" in result.stdout.lower()
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def test_report_failing_script(self):
        """Test report with failing script."""
        # Create temporary Python script that fails
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import nonexistent_module\n")
            temp_file = f.name
        
        try:
            result = runner.invoke(app, ["report-incompatibility", temp_file, "--no-submit"])
            
            # Should fail but handle gracefully
            assert result.exit_code == 1
            assert "Error" in result.stdout or "failed" in result.stdout.lower()
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def test_report_help(self):
        """Test report-incompatibility --help."""
        result = runner.invoke(app, ["report-incompatibility", "--help"])
        assert result.exit_code == 0
        assert "Execute script" in result.stdout


class TestSubmitStackCommand:
    """Test submit-stack command."""
    
    def test_submit_stack_help(self):
        """Test submit-stack --help."""
        result = runner.invoke(app, ["submit-stack", "--help"])
        assert result.exit_code == 0
        assert "Submit a verified stable stack" in result.stdout

    @patch('env_doctor.cli.submit_stack.httpx.Client')
    @patch('env_doctor.cli.submit_stack.RepositoryManager')
    def test_submit_stack_basic(self, mock_repo, mock_httpx):
        """Test basic submit-stack command."""
        # Mock repository manager to return worker URL
        mock_repo_instance = Mock()
        mock_repo_instance.get_worker_url.return_value = "https://mock-worker.dev"
        mock_repo.return_value = mock_repo_instance
        
        # Mock httpx response
        mock_response = Mock()
        mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
        mock_response.status_code = 200
        
        result = runner.invoke(app, ["submit-stack", "test-stack", "--desc", "Test description", "--no-current", "--package", "torch==2.1.0"])
        
        assert result.exit_code == 0
        assert "registered" in result.stdout


class TestIntegration:
    """Integration tests for CLI."""
    
    def test_all_commands_have_help(self):
        """Test that all commands have help text."""
        commands = [
            "update-db",
            "inspect",
            "check",
            "recommend",
            "vram",
            "patch",
            "report-incompatibility",
            "submit-stack"
        ]
        
        for cmd in commands:
            result = runner.invoke(app, [cmd, "--help"])
            assert result.exit_code == 0, f"Command {cmd} --help failed"
            assert len(result.stdout) > 0, f"Command {cmd} has no help text"


# Made with Bob