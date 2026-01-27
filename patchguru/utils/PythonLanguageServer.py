# This file is developed based on the code from the [Testora](https://github.com/michaelpradel/Testora) project by Michael Pradel.
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from pathlib import Path


class PythonLanguageServer:
    def __init__(self, repo_path):
        config = MultilspyConfig.from_dict({"code_language": "python"})
        logger = MultilspyLogger()
        absolute_repo_path = str(Path(repo_path).resolve())
        self.lsp = SyncLanguageServer.create(
            config, logger, absolute_repo_path)

    def get_hover_text(self, file_path, line, column):
        with self.lsp.start_server():
            raw_result = self.lsp.request_hover(file_path, line, column)
            if type(raw_result) == dict and "contents" in raw_result:
                return raw_result["contents"]["value"]
            else:
                return ""

    def get_definition(self, file_path, line, column):
        with self.lsp.start_server():
            raw_result = self.lsp.request_definition(file_path, line, column)
            if type(raw_result) == dict and "targetUri" in raw_result:
                return raw_result["targetUri"]
            else:
                return ""


# for testing
if __name__ == "__main__":
    pass
