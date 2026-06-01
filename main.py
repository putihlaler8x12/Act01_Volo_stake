"""One-shot generator for contracts/Act01_Volo_stake.sol — Volo lane staking platform."""
from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contracts" / "Act01_Volo_stake.sol"

# Fresh anchors for this bundle only
ADDR = [
    "0xfD25f4483C09f80DAAf6B3C7d6E19203554d520c",
    "0x5edDAcEBB231d8692553aAcB03a0fdb21783bEC5",
    "0xFD79a9b461880DA62639167B101ccE68c86aDEB0",
]
HEX32 = [
    "0x349a2cc4e39af8f95d772eb6458350a51755e072f8787ec88283208d191ce8e4",
    "0x96d10a1dd126fb730fc04373b12eef87bc2e9414727ddf6e4942b9573def4648",
    "0xbe4f6d7dbe4131d35bcba8851394fc2ff2c218ee689d188134667e0bb83c73f0",
    "0x5ecbcc909d2cd8c271d6777ea1d5b81c4c0d81259598241d06ee5b252de15863",
    "0x5853fce2d535524ba8c4821bc2d9dc1069826b517cde8258bdc46f114d5db1f4",
    "0xd27fa3e4478caef7feeef053dd2b6ecc3be4e0e4b402e8dd130ca76eb40d2a2c",
]

POOL_COUNT = 28
EPOCH_SLOTS = 36
VIEW_BATCH = 42


def w(lines: list[str], s: str = "") -> None:
    lines.append(s)


def emit_header(la: list[str]) -> None:
    w(la, "// SPDX-License-Identifier: MIT")
    w(la, "pragma solidity ^0.8.24;")
    w(la, "")
    w(la, "/// @title Act01_Volo_stake")
    w(la, '/// @notice Volo stake lanes — codename "kestrel drift mooring"')
    w(la, "/// @dev Epoch-weighted native and ERC20 pools; pull withdrawals; deskFrozen circuit.")
    w(la, "")


def emit_interfaces(la: list[str]) -> None:
    w(la, "interface IVoloERC20 {")
    w(la, "    function balanceOf(address account) external view returns (uint256);")
    w(la, "    function allowance(address owner, address spender) external view returns (uint256);")
    w(la, "    function transfer(address to, uint256 amount) external returns (bool);")
    w(la, "    function transferFrom(address from, address to, uint256 amount) external returns (bool);")
    w(la, "}")
    w(la, "")


def emit_libraries(la: list[str]) -> None:
    w(la, "library VoloMath {")
    w(la, "    error VS_MathOverflow();")
    w(la, "    uint256 internal constant BPS = 10_000;")
    w(la, "    function min(uint256 a, uint256 b) internal pure returns (uint256) {")
    w(la, "        return a < b ? a : b;")
    w(la, "    }")
    w(la, "    function max(uint256 a, uint256 b) internal pure returns (uint256) {")
    w(la, "        return a > b ? a : b;")
    w(la, "    }")
    w(la, "    function mulDivDown(uint256 x, uint256 y, uint256 d) internal pure returns (uint256 z) {")
    w(la, "        unchecked {")
    w(la, "            if (d == 0) revert VS_MathOverflow();")
    w(la, "            z = (x * y) / d;")
    w(la, "        }")
    w(la, "    }")
    w(la, "    function mulDivUp(uint256 x, uint256 y, uint256 d) internal pure returns (uint256 z) {")
    w(la, "        unchecked {")
    w(la, "            if (d == 0) revert VS_MathOverflow();")
    w(la, "            z = (x * y + d - 1) / d;")
    w(la, "        }")
    w(la, "    }")
    w(la, "    function addCap(uint256 a, uint256 b, uint256 cap) internal pure returns (uint256) {")
    w(la, "        unchecked {")
    w(la, "            uint256 s = a + b;")
    w(la, "            if (s < a || s > cap) revert VS_MathOverflow();")
    w(la, "            return s;")
    w(la, "        }")
    w(la, "    }")
    w(la, "}")
    w(la, "")
    w(la, "library VoloSafeERC20 {")
    w(la, "    error VS_TokenCallFailed();")
    w(la, "    error VS_TokenBadReturn();")
    w(la, "    function safeTransfer(IVoloERC20 t, address to, uint256 amt) internal {")
    w(la, "        _call(t, abi.encodeWithSelector(IVoloERC20.transfer.selector, to, amt));")
    w(la, "    }")
    w(la, "    function safeTransferFrom(IVoloERC20 t, address f, address to, uint256 amt) internal {")
    w(la, "        _call(t, abi.encodeWithSelector(IVoloERC20.transferFrom.selector, f, to, amt));")
    w(la, "    }")
    w(la, "    function _call(IVoloERC20 t, bytes memory data) private {")
    w(la, "        (bool ok, bytes memory ret) = address(t).call(data);")
    w(la, "        if (!ok) revert VS_TokenCallFailed();")
    w(la, "        if (ret.length != 0 && (ret.length != 32 || !abi.decode(ret, (bool)))) revert VS_TokenBadReturn();")
    w(la, "    }")
    w(la, "}")
    w(la, "")


def emit_contract_start(la: list[str]) -> None:
    w(la, "contract Act01_Volo_stake {")
    w(la, "    // ── faults ───────────────────────────────────────────────────────────")
    errs = [
