from algohlper.services.problem_parser import parse_problem_spec


def test_parse_problem_spec_extracts_sections() -> None:
    content = """# A + B Problem

题目描述
给定两个整数，输出它们的和。

输入格式
```text
a b
```

输出格式
```text
输出一个整数
```

数据范围
- 1 <= a <= 1e9
- 1 <= b <= 1e9

样例输入
```text
1 2
```

样例输出
```text
3
```
"""
    spec = parse_problem_spec(content)
    assert spec.title == "A + B Problem"
    assert "给定两个整数" in spec.statement
    assert "a b" in spec.input_format
    assert "输出一个整数" in spec.output_format
    assert spec.samples[0].input.strip() == "1 2"
    assert spec.samples[0].output.strip() == "3"
    assert spec.constraints["a"] == "1 <= a <= 1e9"
