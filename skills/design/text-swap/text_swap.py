# -*- coding: utf-8 -*-
"""text-swap 核心库:图片取字填字(擦除/抠字/贴字),周记表项目 2026-10 验证
用法示例:
  from text_swap import load, erase, cut_alpha, stamp
  F, gray, bg = load('img.png')
  F = erase(F, gray, [(x0,x1,y0,y1)])           # 擦旧字
  a, core_ink = cut_alpha(gray, bg, x0,x1,y0,y1) # 抠笔迹
  stamp(F, [a1, a0], right_x=960, bottom=242, heights=[42,42], ink=(47,48,51), seed='k')
"""
import random
import numpy as np
import cv2
from PIL import Image, ImageFilter


def load(path):
    """返回 (RGB float图, 灰度, 纸底中值图)"""
    src = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    gray = src.mean(axis=2)
    bg = cv2.medianBlur(gray.astype(np.uint8), 51).astype(np.float32)
    return src, gray, bg


def erase(F, gray, zones, thr=178, r=5):
    """就地擦除 zones=[(x0,x1,y0,y1)] 内文字, 返回擦后的 F"""
    mask = np.zeros(gray.shape, np.uint8)
    for x0, x1, y0, y1 in zones:
        m = (gray[y0:y1, x0:x1] < thr).astype(np.uint8) * 255
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        mask[y0:y1, x0:x1] = m
    out = cv2.inpaint(F.astype(np.uint8)[:, :, ::-1], mask, r, cv2.INPAINT_TELEA)[:, :, ::-1]
    F[...] = out.astype(np.float32)
    return F


def cut_alpha(gray, bg, x0, x1, y0, y1):
    """抠笔迹:返回 (alpha裁到bbox, 核心墨色RGB)。伽马压灰裙边+陡阈值,防贴图灰晕"""
    g = gray[y0:y1, x0:x1]
    a = np.clip((bg[y0:y1, x0:x1] - g) / np.maximum(bg[y0:y1, x0:x1] - 50, 30), 0, 1) ** 1.6
    a[a < 0.35] = 0
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.3))).astype(np.float32) / 255.0
    a[a < 0.2] = 0
    ys, xs = np.nonzero(a > 0.1)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return a


def _scale(a, h):
    w = max(1, round(a.shape[1] * h / a.shape[0]))
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)).astype(np.float32) / 255.0


def stamp(F, alphas, right_x, bottom, heights, ink=(47, 48, 51), seed="s", gap=2, rot_deg=1.5):
    """把多个字 alpha 从右往左排成一组贴到 F:右对齐 right_x,底对齐 bottom
    alphas/heights 一一对应;ink=统一墨色;seed 固定可复现"""
    rng = random.Random(seed)
    parts = []
    for a, h in zip(alphas, heights):
        s = _scale(a, h)
        im = Image.fromarray((s * 255).astype(np.uint8)).rotate(rng.uniform(-rot_deg, rot_deg), expand=True, resample=Image.BICUBIC, fillcolor=0)
        parts.append(np.asarray(im).astype(np.float32) / 255.0)
    H = max(p.shape[0] for p in parts)  # 旋转expand后取实际最大高
    W = sum(p.shape[1] for p in parts) + gap * (len(parts) - 1)
    comb = np.zeros((H, W))
    x = 0
    for p in parts:
        comb[H - p.shape[0]:, x:x + p.shape[1]] = p
        x += p.shape[1] + gap
    comb = np.asarray(Image.fromarray((comb * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4))).astype(np.float32) / 255.0
    y0, x0 = int(bottom - comb.shape[0] + rng.randint(-1, 1)), int(right_x - comb.shape[1])
    reg = F[y0:y0 + comb.shape[0], x0:x0 + comb.shape[1]]
    a3 = comb[..., None]
    F[y0:y0 + comb.shape[0], x0:x0 + comb.shape[1]] = reg * (1 - a3) + np.array(ink, np.float32)[None, None, :] * a3
    return x0, y0, W, H


def save(F, path, quality=95):
    Image.fromarray(F.clip(0, 255).astype(np.uint8)).save(path, quality=quality)
