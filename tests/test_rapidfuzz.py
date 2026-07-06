"""RapidFuzz 安装验证测试。

测试 RapidFuzz 对三组典型通信设计点位名称的匹配得分。
"""
from rapidfuzz import fuzz

pairs = [
    ("A/B社区", "AB社区"),
    ("人民路机房", "人民路机房（最终）"),
    ("社区名称", "标准社区名称"),
]

print("RapidFuzz 字符串匹配测试")
print("=" * 60)

for a, b in pairs:
    ratio = fuzz.ratio(a, b)
    partial = fuzz.partial_ratio(a, b)
    token_sort = fuzz.token_sort_ratio(a, b)
    token_set = fuzz.token_set_ratio(a, b)
    w_ratio = fuzz.WRatio(a, b)

    print(f'"{a}"  vs  "{b}"')
    print(f"  ratio:        {ratio:6.1f}")
    print(f"  partial:      {partial:6.1f}")
    print(f"  token_sort:   {token_sort:6.1f}")
    print(f"  token_set:    {token_set:6.1f}")
    print(f"  WRatio:       {w_ratio:6.1f}")
    print()

print("=" * 60)
print("RapidFuzz 安装验证成功")
