# noisedither

## 题面（可直接粘贴）

抖动 + 噪声整形。约束：量化噪声频谱必须向高频整形（低频能量下降 ≥6 dB）；输出均值与输入均值差 ≤1e-3；同种子可复现；100 万样本不超过 400 ms；非法参数报错。验收：cd noisedither && python -m pytest tests -q -k dither。

## 边界要求（评审侧隐藏用例判分）

- 并发安全
- 非有限输入分类报错
- 性能上界按题面

## 运行方式

```bash
cd noisedither && python -m pytest tests -q
```

初始 15 failed。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：音视频处理
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
