import "./CharacterDetails.css";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterDetails } from "../../services/api.js";

const DETAIL_TABS = [
  ["stats", "스탯"],
  ["equipment", "장비"],
  ["symbols", "심볼"],
  ["skills", "6차 / HEXA"],
  ["link", "링크 스킬"],
  ["union", "유니온"]
];

const STAT_LABELS = {
  STR:"STR",DEX:"DEX",INT:"INT",LUK:"LUK",
  "보스 몬스터 공격 시 데미지":"보스 데미지",
  "몬스터 방어율 무시":"방어율 무시",
  "일반 몬스터 공격 시 데미지":"일반 몬스터 데미지"
};

// FILE_TOO_LARGE_SPLIT_STRATEGY
export default function CharacterDetails() {
  return null;
}
