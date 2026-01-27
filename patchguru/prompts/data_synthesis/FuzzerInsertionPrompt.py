from patchguru.utils.Logger import get_logger


class FuzzerInsertionPrompt:
    def __init__(self):
        self.logger = get_logger("fuzzer_insertion")
        self.logger.debug("FuzzerInsertionPrompt initialized")

    def create_prompt(
        self,
        test_driver_code: str,
    ) -> str:
        template = """
You are a code reviewing assistant that specializes in inserting fuzzers into test drivers to ensure comprehensive testing of the code.

# Input

You will be provided a test driver that is used to validate the expected relationship between two versions of a function: before and after a pull request. This test driver contains source code of the function(s) being tested and specifications that describe the expected behavior of the function(s) in the form of Python assertions, as follows:

## Test Driver

```python
{test_driver_code}
```

# Instructions

## Task

Your task is to replace existing test cases in the provided test driver with Atheris Fuzzer (https://github.com/google/atheris) that generate random inputs to thoroughly test the function(s). You should do step-by-step reasoning as follows:
- Analyze the provided test driver to understand code structure.
- Identify the specific parts of the code that need to be replaced with Atheris Fuzzer.
- Identify the data types of the function parameters and return types.
- Identify suitable FuzzedDataProvider for the function parameters based on their data types. Please follows Atheris's instructions below to use Atheris and its FuzzedDataProvider:

```
# Using Atheris
Example
#!/usr/bin/python3

import atheris

def TestOneInput(data):
   test_driver_code(data)

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
When fuzzing Python, Atheris will report a failure if the Python code under test throws an uncaught exception.

# FuzzedDataProvider
Often, a bytes object is not convenient input to your code being fuzzed. Similar to libFuzzer, we provide a FuzzedDataProvider to translate these bytes into other input forms.

You can construct the FuzzedDataProvider with:

fdp = atheris.FuzzedDataProvider(input_bytes)
The FuzzedDataProvider then supports the following functions:

def ConsumeBytes(count: int)
Consume count bytes.

def ConsumeUnicode(count: int)
Consume unicode characters. Might contain surrogate pair characters, which according to the specification are invalid in this situation. However, many core software tools (e.g. Windows file paths) support them, so other software often needs to too.

def ConsumeUnicodeNoSurrogates(count: int)
Consume unicode characters, but never generate surrogate pair characters.

def ConsumeString(count: int)
Alias for ConsumeBytes in Python 2, or ConsumeUnicode in Python 3.

def ConsumeInt(int: bytes)
Consume a signed integer of the specified size (when written in two's complement notation).

def ConsumeUInt(int: bytes)
Consume an unsigned integer of the specified size.

def ConsumeIntInRange(min: int, max: int)
Consume an integer in the range [min, max].

def ConsumeIntList(count: int, bytes: int)
Consume a list of count integers of size bytes.

def ConsumeIntListInRange(count: int, min: int, max: int)
Consume a list of count integers in the range [min, max].

def ConsumeFloat()
Consume an arbitrary floating-point value. Might produce weird values like NaN and Inf.

def ConsumeRegularFloat()
Consume an arbitrary numeric floating-point value; never produces a special type like NaN or Inf.

def ConsumeProbability()
Consume a floating-point value in the range [0, 1].

def ConsumeFloatInRange(min: float, max: float)
Consume a floating-point value in the range [min, max].

def ConsumeFloatList(count: int)
Consume a list of count arbitrary floating-point values. Might produce weird values like NaN and Inf.

def ConsumeRegularFloatList(count: int)
Consume a list of count arbitrary numeric floating-point values; never produces special types like NaN or Inf.

def ConsumeProbabilityList(count: int)
Consume a list of count floats in the range [0, 1].

def ConsumeFloatListInRange(count: int, min: float, max: float)
Consume a list of count floats in the range [min, max]

def PickValueInList(l: list)
Given a list, pick a random value

def ConsumeBool()
Consume either True or False.
```

## Constraints
- New test driver should be a valid Python code that can be executed with Atheris.
- New test driver should not change the source code of the function(s) being tested and assertions. It should only replace the existing test cases with Atheris Fuzzer through FuzzedDataProvider.

# Output Format

Provide your response in the following format:

<reasoning>
[Put your reasoning chain here including the analysis of the test driver code and how you arrived at the new test driver with Atheris Fuzzer.]
</reasoning>

<new_test_driver>
[Put the new test driver code here that uses Atheris Fuzzer. Ensure that the code is executable and maintains the original semantics of the test driver.]
</new_test_driver>
        """
        query = template.format(
            test_driver_code=test_driver_code,
        )
        self.logger.debug(f"Created prompt:\n {query}")
        self.logger.debug("FuzzerInsertionPrompt created successfully")

        return query


    def parse_answer(self, answer):
        self.logger.debug(f"Parsing answer with length: {len(answer)}")

        if "<reasoning>" not in answer or "</reasoning>" not in answer:
            self.logger.error("Missing required tag: <reasoning>")
            return None

        if "<new_test_driver>" not in answer or "</new_test_driver>" not in answer:
            self.logger.error("Missing required tag: <new_test_driver>")
            return None

        results = {}
        try:
            reasoning_start = answer.index("<reasoning>") + len("<reasoning>")
            reasoning_end = answer.index("</reasoning>")
            results["reasoning"] = answer[reasoning_start:reasoning_end].strip()

            new_test_driver_start = answer.index("<new_test_driver>") + len("<new_test_driver>")
            new_test_driver_end = answer.index("</new_test_driver>")
            new_test_driver = answer[new_test_driver_start:new_test_driver_end].strip()

            if "```" in new_test_driver:
                if "```python" in new_test_driver:
                    new_test_driver = new_test_driver.split("```python")[1].split("```")[0].strip()
                else:
                    new_test_driver = new_test_driver.split("```")[1].split("```")[0].strip()

            results["new_test_driver"] = new_test_driver
        except ValueError as e:
            self.logger.error(f"Error parsing the answer: {e}")
            return None

        self.logger.debug(f"Parsed answer: {results}")
        return results
