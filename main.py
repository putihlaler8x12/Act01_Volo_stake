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
        ("VS_NotPitMaster", "Caller is not pitMaster."),
        ("VS_DeskFrozen", "Operations halted while deskFrozen."),
        ("VS_ZeroAddr", "Zero address rejected."),
        ("VS_ZeroAmt", "Zero amount rejected."),
        ("VS_Reentered", "Reentrancy guard tripped."),
        ("VS_PoolMissing", "Pool id not provisioned."),
        ("VS_PoolClosed", "Pool not accepting deposits."),
        ("VS_LockActive", "Stake still inside lock window."),
        ("VS_InsufficientStake", "Withdraw exceeds position."),
        ("VS_InsufficientReward", "Reward bucket empty."),
        ("VS_CapExceeded", "Pool or lane cap exceeded."),
        ("VS_BadEpoch", "Epoch index out of range."),
        ("VS_BadBps", "Basis points out of allowed band."),
        ("VS_NativeOnly", "Pool expects native asset."),
        ("VS_TokenOnly", "Pool expects ERC20 asset."),
        ("VS_TokenUnset", "ERC20 stake token not configured."),
        ("VS_AlreadySet", "Immutable lane anchor already bound."),
        ("VS_BelowMin", "Deposit below pool minimum."),
        ("VS_AboveMax", "Deposit above pool maximum."),
        ("VS_NoReward", "Nothing to claim."),
        ("VS_BadHandoff", "Invalid pitMaster handoff target."),
        ("VS_EpochStale", "Epoch snapshot not yet advanced."),
        ("VS_LineVoid", "Line id retired."),
        ("VS_DigestMismatch", "Attestation digest mismatch."),
    ]
    for name, _ in errs:
        w(la, f"    error {name}();")
    for i in range(24, 58):
        w(la, f"    error VS_LaneFault_{i}();")
    w(la, "")
    w(la, "    // ── events (short verbs) ─────────────────────────────────────────────")
    w(la, "    event Opened(uint256 indexed poolId, uint8 assetKind, uint64 lockSecs, uint256 rewardBps);")
    w(la, "    event Topped(address indexed staker, uint256 indexed poolId, uint256 amount, uint64 unlockAt);")
    w(la, "    event Pulled(address indexed staker, uint256 indexed poolId, uint256 amount, uint256 rewardPaid);")
    w(la, "    event Claimed(address indexed staker, uint256 indexed poolId, uint256 reward);")
    w(la, "    event Compounded(address indexed staker, uint256 indexed poolId, uint256 addedPrincipal);")
    w(la, "    event EpochShifted(uint256 indexed epochId, uint64 wallTime, uint256 totalStaked);")
    w(la, "    event Frozen(bool deskFrozen, address indexed by);")
    w(la, "    event Handed(address indexed prev, address indexed next);")
    w(la, "    event Tuned(uint256 indexed poolId, uint256 rewardBps, uint256 minDeposit);")
    for i in range(12):
        w(la, f"    event Pulse_{i}(uint256 indexed lineId, address indexed actor, uint256 weiAmt);")
    w(la, "")


def emit_types_and_state(la: list[str]) -> None:
    w(la, "    enum VoloAssetKind { Native, Erc20 }")
    w(la, "    enum VoloPoolPhase { Dormant, Live, Sunset }")
    w(la, "")
    w(la, "    struct VoloPoolLine {")
    w(la, "        VoloAssetKind assetKind;")
    w(la, "        VoloPoolPhase phase;")
    w(la, "        uint64 lockSeconds;")
    w(la, "        uint64 openedAt;")
    w(la, "        uint256 rewardBpsAnnual;")
    w(la, "        uint256 minDepositWei;")
    w(la, "        uint256 maxDepositWei;")
    w(la, "        uint256 capWei;")
    w(la, "        uint256 totalStakedWei;")
    w(la, "        uint256 rewardAccPerShare;")
    w(la, "        uint256 lastAccrualTs;")
    w(la, "        bytes32 laneTag;")
    w(la, "    }")
    w(la, "")
    w(la, "    struct VoloPosition {")
    w(la, "        uint256 principalWei;")
    w(la, "        uint256 rewardDebt;")
    w(la, "        uint64 unlockAt;")
    w(la, "        uint64 lastTouch;")
    w(la, "        uint32 epochJoined;")
    w(la, "        bool exists;")
    w(la, "    }")
    w(la, "")
    w(la, "    struct VoloEpochCell {")
    w(la, "        uint64 startedAt;")
    w(la, "        uint256 weightSum;")
    w(la, "        uint256 distributedWei;")
    w(la, "        bytes32 mixHA;")
    w(la, "        bytes32 mixHB;")
    w(la, "    }")
    w(la, "")
    w(la, "    uint256 public constant VOLO_BPS = 10_000;")
    w(la, "    uint256 public constant VOLO_YEAR = 31_536_000;")
    w(la, "    uint256 public constant VOLO_MAX_ANNUAL_BPS = 2_500;")
    w(la, "")
    for i, h in enumerate(HEX32):
        w(la, f"    bytes32 private constant _SALT_{i} = {h};")
    w(la, "")
    w(la, "    address public immutable ADDRESS_A;")
    w(la, "    address public immutable ADDRESS_B;")
    w(la, "    address public immutable ADDRESS_C;")
    w(la, "    IVoloERC20 public immutable stakeToken;")
    w(la, "")
    w(la, "    address public pitMaster;")
    w(la, "    bool public deskFrozen;")
    w(la, "    uint256 public globalEpoch;")
    w(la, "    uint256 public lineNonce;")
    w(la, "    uint256 public totalNativeHeld;")
    w(la, "    uint256 public totalRewardMinted;")
    w(la, "")
    w(la, "    mapping(uint256 => VoloPoolLine) public pools;")
    w(la, "    mapping(uint256 => mapping(address => VoloPosition)) public positions;")
    w(la, "    mapping(uint256 => VoloEpochCell) public epochs;")
    w(la, "    mapping(address => uint256) public stakerLaneMask;")
    w(la, "    mapping(bytes32 => bool) public attestationConsumed;")
    w(la, "    uint256 private _reentrancyFlag;")
