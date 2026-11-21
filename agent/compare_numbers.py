import json
import re
from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition

_OPERATORS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _parse_params(raw: str | None, *required_keys: str) -> dict[str, Any]:
    if not raw or raw == "null":
        if required_keys:
            raise ValueError(f"参数为空，需要字段: {list(required_keys)}")
        return {}
    try:
        params = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}") from e
    if not isinstance(params, dict):
        raise ValueError(f"参数必须是对象，得到: {type(params).__name__}")
    missing = [k for k in required_keys if k not in params]
    if missing:
        raise ValueError(f"缺少必填字段: {missing}")
    return params


def _ocr_text(detail: Any, default: str = "") -> str:
    if detail is None or not detail.hit:
        return default
    text = getattr(detail.best_result, "text", None)
    return text if isinstance(text, str) else default


@AgentServer.custom_recognition("CompareNumbers")
class CompareNumbers(CustomRecognition):
    """通用数字比较识别，替代「OCR + expected 正则」的数字判断。

    参数（custom_recognition_param）：
        operator: < <= > >= == !=  必填，比较运算符
        value: number            可选，与固定值比较；不传则两个数互比
        roi: [x, y, w, h]        可选，OCR 区域；不传则用 recognition 节点上配的 roi（推荐）
        separator: str           可选，分隔符（如 "/"），自动构建 (\\d+)sep(\\d+)
        pattern: str             可选，自定义正则，需两个捕获组
        split_at: int            可选，只识别到一个数字时按此位数切成两个
        index: 0 | 1             可选，比第一个数还是第二个数（0=first 默认，1=second）

    roi 来源优先级：argv.roi（recognition 节点配置）> custom_recognition_param.roi。
    数字提取优先级：pattern > separator > 自动（取前两个数字，单个按 split_at 切）。
    value 存在时，用第 index 个数与 value 比较；value 不存在时，用 first 与 second 互比。

    detail 返回：
        { ocr_text, first, second, target, operator, value, result, reason? }
    命中时 box 为 OCR 位置，不命中时 box=None。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        try:
            params = _parse_params(argv.custom_recognition_param, "operator")
        except ValueError as e:
            return CustomRecognition.AnalyzeResult(box=None, detail={"reason": str(e)})

        # roi 优先用 recognition 节点上配置的 argv.roi，param.roi 仅作兼容兜底
        roi = list(argv.roi) if argv.roi and any(argv.roi) else params.get("roi", [0, 0, 0, 0])
        operator = params["operator"]
        if operator not in _OPERATORS:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"reason": f"不支持的运算符: {operator}"},
            )

        value = params.get("value")
        pattern = params.get("pattern")
        separator = params.get("separator")
        split_at = params.get("split_at")
        index = params.get("index", 0)
        if index not in (0, 1):
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"reason": f"index 只能是 0 或 1，得到: {index}"},
            )

        ocr_detail = context.run_recognition(
            "OCR",
            argv.image,
            {"OCR": {"recognition": "OCR", "roi": roi, "expected": ".+", "only_rec": True}},
        )
        if ocr_detail is None or not ocr_detail.hit:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"reason": "OCR 未识别到文本"},
            )

        text = _ocr_text(ocr_detail)
        if not text:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"reason": "OCR 返回空文本"},
            )

        numbers = self._extract_numbers(text, pattern, separator, split_at)
        if numbers is None and value is not None:
            # 单数字场景：把这一个数字放到 index 指定的位置，另一位置用 value 占位
            single = re.search(r"\d+", text)
            if single:
                num = int(single.group())
                numbers = (num, int(value)) if index == 0 else (int(value), num)
        if numbers is None:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"ocr_text": text, "reason": f"无法从文本中提取两个数字: {text}"},
            )

        first, second = numbers
        if value is not None:
            target = first if index == 0 else second
            result = _OPERATORS[operator](target, value)
        else:
            # 两数互比时 index 无意义，始终 first vs second
            target = first
            result = _OPERATORS[operator](first, second)

        detail: dict[str, Any] = {
            "ocr_text": text,
            "first": first,
            "second": second,
            "target": target,
            "operator": operator,
            "value": value,
            "result": result,
        }
        if not result:
            detail["reason"] = f"比较结果不满足: {target} {operator} {value if value is not None else second} = false"
            return CustomRecognition.AnalyzeResult(box=None, detail=detail)

        return CustomRecognition.AnalyzeResult(box=ocr_detail.box, detail=detail)

    @staticmethod
    def _extract_numbers(
        text: str,
        pattern: str | None,
        separator: str | None,
        split_at: int | None,
    ) -> tuple[int, int] | None:
        if pattern:
            m = re.search(pattern, text)
            if m and m.lastindex and m.lastindex >= 2:
                return (int(m.group(1)), int(m.group(2)))
            return None

        if separator:
            escaped = re.escape(separator)
            m = re.search(rf"(\d+)\s*{escaped}\s*(\d+)", text)
            if m:
                return (int(m.group(1)), int(m.group(2)))
            return None

        nums = re.findall(r"\d+", text)
        if len(nums) >= 2:
            return (int(nums[0]), int(nums[1]))
        if len(nums) == 1 and split_at is not None:
            num_str = nums[0]
            if 0 < split_at < len(num_str):
                return (int(num_str[:split_at]), int(num_str[split_at:]))
        return None
