import logging
import os
import shutil
import tempfile

from unittest import TestCase, mock

from parameterized import parameterized

from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import WorkflowFailedError
from tests.testing_utils import read_link_without_junction_prefix

logger = logging.getLogger("aws_lambda_builders.workflows.nodejs_npm.workflow")


class TestNodejsNpmWorkflow(TestCase):
    """
    Verifies that `nodejs_npm` workflow works by building a Lambda using NPM
    """

    TEST_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "testdata")

    def setUp(self):
        self.artifacts_dir = tempfile.mkdtemp()
        self.scratch_dir = tempfile.mkdtemp()
        self.dependencies_dir = tempfile.mkdtemp()

        # use this so tests don't modify actual testdata, and we can parallelize
        self.temp_dir = tempfile.mkdtemp()
        self.temp_testdata_dir = os.path.join(self.temp_dir, "testdata")
        shutil.copytree(self.TEST_DATA_FOLDER, self.temp_testdata_dir)

        self.no_deps = os.path.join(self.TEST_DATA_FOLDER, "no-deps")

        self.builder = LambdaBuilder(language="nodejs", dependency_manager="npm", application_framework=None)

    def tearDown(self):
        shutil.rmtree(self.artifacts_dir)
        shutil.rmtree(self.scratch_dir)
        shutil.rmtree(self.dependencies_dir)
        shutil.rmtree(self.temp_dir)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_without_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_without_manifest(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "no-manifest")

        with mock.patch.object(logger, "warning") as mock_warning:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
            )

        expected_files = {"app.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        mock_warning.assert_called_once_with("package.json file not found. Continuing the build without dependencies.")
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_and_excludes_hidden_aws_sam(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "excluded-files")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_remote_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_npmrc(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npmrc")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

        expected_modules = {"fake-http-request"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

    @parameterized.expand(
        [
            ("nodejs12.x", "package-lock"),
            ("nodejs14.x", "package-lock"),
            ("nodejs16.x", "package-lock"),
            ("nodejs18.x", "package-lock"),
            ("nodejs12.x", "shrinkwrap"),
            ("nodejs14.x", "shrinkwrap"),
            ("nodejs16.x", "shrinkwrap"),
            ("nodejs18.x", "shrinkwrap"),
            ("nodejs12.x", "package-lock-and-shrinkwrap"),
            ("nodejs14.x", "package-lock-and-shrinkwrap"),
            ("nodejs16.x", "package-lock-and-shrinkwrap"),
            ("nodejs18.x", "package-lock-and-shrinkwrap"),
        ]
    )
    def test_builds_project_with_lockfile(self, runtime, dir_name):
        expected_files_common = {"package.json", "included.js", "node_modules"}
        expected_files_by_dir_name = {
            "package-lock": {"package-lock.json"},
            "shrinkwrap": {"npm-shrinkwrap.json"},
            "package-lock-and-shrinkwrap": {"package-lock.json", "npm-shrinkwrap.json"},
        }

        source_dir = os.path.join(self.TEST_DATA_FOLDER, dir_name)

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
        )

        expected_files = expected_files_common.union(expected_files_by_dir_name[dir_name])

        output_files = set(os.listdir(self.artifacts_dir))

        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_fails_if_npm_cannot_resolve_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "broken-deps")

        with self.assertRaises(WorkflowFailedError) as ctx:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
            )

        self.assertIn("No matching version found for aws-sdk@2.997.999", str(ctx.exception))

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_remote_dependencies_without_download_dependencies_with_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_remote_dependencies_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
        )

        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.artifacts_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

        expected_modules = {"minimal-request-promise"}
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertEqual(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_with_remote_dependencies_without_download_dependencies_without_dependencies_dir(
        self, runtime
    ):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        with mock.patch.object(logger, "info") as mock_info:
            self.builder.build(
                source_dir,
                self.artifacts_dir,
                self.scratch_dir,
                os.path.join(source_dir, "package.json"),
                runtime=runtime,
                dependencies_dir=None,
                download_dependencies=False,
            )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_builds_project_without_combine_dependencies(self, runtime):
        source_dir = os.path.join(self.TEST_DATA_FOLDER, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=True,
            combine_dependencies=False,
        )

        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

        expected_modules = "minimal-request-promise"
        output_modules = set(os.listdir(os.path.join(self.dependencies_dir, "node_modules")))
        self.assertIn(expected_modules, output_modules)

        expected_dependencies_files = {"node_modules"}
        output_dependencies_files = set(os.listdir(os.path.join(self.dependencies_dir)))
        self.assertNotIn(expected_dependencies_files, output_dependencies_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_build_in_source_with_download_dependencies(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_build_in_source_with_download_dependencies_local_dependency(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "with-local-dependency")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"local-dependency", "minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_build_in_source_with_download_dependencies_and_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_build_in_source_with_download_dependencies_and_dependencies_dir_without_combine_dependencies(
        self, runtime
    ):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            combine_dependencies=False,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_build_in_source_reuse_saved_dependencies_dir(self, runtime):
        source_dir = os.path.join(self.temp_testdata_dir, "npm-deps")

        # first build to save to dependencies_dir
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime=runtime,
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
        )

        # cleanup artifacts_dir to make sure we use dependencies from dependencies_dir
        for filename in os.listdir(self.artifacts_dir):
            file_path = os.path.join(self.artifacts_dir, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path)

        # build again without downloading dependencies
        self.builder.build(
            source_dir,
            self.artifacts_dir,
            self.scratch_dir,
            os.path.join(source_dir, "package.json"),
            runtime="nodejs16.x",
            build_in_source=True,
            dependencies_dir=self.dependencies_dir,
            download_dependencies=False,
        )

        # dependencies installed in source folder
        source_node_modules = os.path.join(source_dir, "node_modules")
        self.assertTrue(os.path.isdir(source_node_modules))
        expected_node_modules_contents = {"minimal-request-promise", ".package-lock.json"}
        self.assertEqual(set(os.listdir(source_node_modules)), expected_node_modules_contents)

        # source dependencies are symlinked to artifacts dir
        artifacts_node_modules = os.path.join(self.artifacts_dir, "node_modules")
        self.assertTrue(os.path.islink(artifacts_node_modules))
        self.assertEqual(read_link_without_junction_prefix(artifacts_node_modules), source_node_modules)

        # source dependencies are symlinked to dependencies dir
        dependencies_dir_node_modules = os.path.join(self.dependencies_dir, "node_modules")
        self.assertTrue(os.path.islink(dependencies_dir_node_modules))
        self.assertEqual(read_link_without_junction_prefix(dependencies_dir_node_modules), source_node_modules)

        # expected output
        expected_files = {"package.json", "included.js", "node_modules"}
        output_files = set(os.listdir(self.artifacts_dir))
        self.assertEqual(expected_files, output_files)
