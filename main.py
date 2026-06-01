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
    w(la, "")


def emit_modifiers(la: list[str]) -> None:
    w(la, "    modifier nonReentrant() {")
    w(la, "        if (_reentrancyFlag == 2) revert VS_Reentered();")
    w(la, "        _reentrancyFlag = 2;")
    w(la, "        _;")
    w(la, "        _reentrancyFlag = 1;")
    w(la, "    }")
    w(la, "")
    w(la, "    modifier onlyPitMaster() {")
    w(la, "        if (msg.sender != pitMaster) revert VS_NotPitMaster();")
    w(la, "        _;")
    w(la, "    }")
    w(la, "")
    w(la, "    modifier whenDeskLive() {")
    w(la, "        if (deskFrozen) revert VS_DeskFrozen();")
    w(la, "        _;")
    w(la, "    }")
    w(la, "")


def emit_constructor(la: list[str]) -> None:
    w(la, "    constructor(address pitMaster_, address stakeToken_) {")
    w(la, "        if (pitMaster_ == address(0)) revert VS_ZeroAddr();")
    w(la, f"        ADDRESS_A = {ADDR[0]};")
    w(la, f"        ADDRESS_B = {ADDR[1]};")
    w(la, f"        ADDRESS_C = {ADDR[2]};")
    w(la, "        pitMaster = pitMaster_;")
    w(la, "        stakeToken = IVoloERC20(stakeToken_);")
    w(la, "        _reentrancyFlag = 1;")
    w(la, "        globalEpoch = 1;")
    w(la, "        _seedEpoch(1);")
    w(la, "        _bootstrapPools();")
    w(la, "    }")
    w(la, "")


def emit_admin(la: list[str]) -> None:
    w(la, "    function transferRole(address nextPitMaster) external onlyPitMaster {")
    w(la, "        if (nextPitMaster == address(0)) revert VS_BadHandoff();")
    w(la, "        address prev = pitMaster;")
    w(la, "        pitMaster = nextPitMaster;")
    w(la, "        emit Handed(prev, nextPitMaster);")
    w(la, "    }")
    w(la, "")
    w(la, "    function setDeskFrozen(bool v) external onlyPitMaster {")
    w(la, "        deskFrozen = v;")
    w(la, "        emit Frozen(v, msg.sender);")
    w(la, "    }")
    w(la, "")
    w(la, "    function tunePool(uint256 poolId, uint256 rewardBps, uint256 minDeposit) external onlyPitMaster {")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.phase == VoloPoolPhase.Dormant) revert VS_PoolMissing();")
    w(la, "        if (rewardBps > VOLO_MAX_ANNUAL_BPS) revert VS_BadBps();")
    w(la, "        p.rewardBpsAnnual = rewardBps;")
    w(la, "        p.minDepositWei = minDeposit;")
    w(la, "        emit Tuned(poolId, rewardBps, minDeposit);")
    w(la, "    }")
    w(la, "")
    w(la, "    function sunsetPool(uint256 poolId) external onlyPitMaster {")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.phase == VoloPoolPhase.Dormant) revert VS_PoolMissing();")
    w(la, "        p.phase = VoloPoolPhase.Sunset;")
    w(la, "    }")
    w(la, "")
    w(la, "    function advanceEpoch() external onlyPitMaster whenDeskLive {")
    w(la, "        uint256 next = globalEpoch + 1;")
    w(la, f"        if (next > {EPOCH_SLOTS}) revert VS_BadEpoch();")
    w(la, "        globalEpoch = next;")
    w(la, "        _seedEpoch(next);")
    w(la, "        uint256 ts = block.timestamp;")
    w(la, "        uint256 staked = _aggregateStaked();")
    w(la, "        emit EpochShifted(next, uint64(ts), staked);")
    w(la, "    }")
    w(la, "")


def emit_stake_ops(la: list[str]) -> None:
    w(la, "    function depositNative(uint256 poolId) external payable nonReentrant whenDeskLive {")
    w(la, "        if (msg.value == 0) revert VS_ZeroAmt();")
    w(la, "        _deposit(poolId, msg.sender, msg.value, true);")
    w(la, "    }")
    w(la, "")
    w(la, "    function depositToken(uint256 poolId, uint256 amount) external nonReentrant whenDeskLive {")
    w(la, "        if (amount == 0) revert VS_ZeroAmt();")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.assetKind != VoloAssetKind.Erc20) revert VS_TokenOnly();")
    w(la, "        if (address(stakeToken) == address(0)) revert VS_TokenUnset();")
    w(la, "        VoloSafeERC20.safeTransferFrom(stakeToken, msg.sender, address(this), amount);")
    w(la, "        _deposit(poolId, msg.sender, amount, false);")
    w(la, "    }")
    w(la, "")
    w(la, "    function withdraw(uint256 poolId, uint256 amount) external nonReentrant whenDeskLive {")
    w(la, "        if (amount == 0) revert VS_ZeroAmt();")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.phase == VoloPoolPhase.Dormant) revert VS_PoolMissing();")
    w(la, "        VoloPosition storage pos = positions[poolId][msg.sender];")
    w(la, "        if (!pos.exists) revert VS_InsufficientStake();")
    w(la, "        if (block.timestamp < pos.unlockAt) revert VS_LockActive();")
    w(la, "        if (amount > pos.principalWei) revert VS_InsufficientStake();")
    w(la, "        _accruePool(poolId);")
    w(la, "        uint256 reward = _pendingReward(poolId, msg.sender);")
    w(la, "        pos.principalWei -= amount;")
    w(la, "        pos.rewardDebt = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        p.totalStakedWei -= amount;")
    w(la, "        if (p.assetKind == VoloAssetKind.Native) {")
    w(la, "            totalNativeHeld -= amount;")
    w(la, "            _pushNative(msg.sender, amount + reward);")
    w(la, "        } else {")
    w(la, "            VoloSafeERC20.safeTransfer(stakeToken, msg.sender, amount);")
    w(la, "            if (reward > 0) VoloSafeERC20.safeTransfer(stakeToken, msg.sender, reward);")
    w(la, "        }")
    w(la, "        if (reward > 0) totalRewardMinted += reward;")
    w(la, "        emit Pulled(msg.sender, poolId, amount, reward);")
    w(la, "    }")
    w(la, "")
    w(la, "    function claimRewards(uint256 poolId) external nonReentrant whenDeskLive {")
    w(la, "        VoloPosition storage pos = positions[poolId][msg.sender];")
    w(la, "        if (!pos.exists) revert VS_NoReward();")
    w(la, "        _accruePool(poolId);")
    w(la, "        uint256 reward = _pendingReward(poolId, msg.sender);")
    w(la, "        if (reward == 0) revert VS_NoReward();")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        pos.rewardDebt = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        if (p.assetKind == VoloAssetKind.Native) {")
    w(la, "            _pushNative(msg.sender, reward);")
    w(la, "        } else {")
    w(la, "            VoloSafeERC20.safeTransfer(stakeToken, msg.sender, reward);")
    w(la, "        }")
    w(la, "        totalRewardMinted += reward;")
    w(la, "        emit Claimed(msg.sender, poolId, reward);")
    w(la, "    }")
    w(la, "")
    w(la, "    function compound(uint256 poolId) external nonReentrant whenDeskLive {")
    w(la, "        VoloPosition storage pos = positions[poolId][msg.sender];")
    w(la, "        if (!pos.exists) revert VS_NoReward();")
    w(la, "        _accruePool(poolId);")
    w(la, "        uint256 reward = _pendingReward(poolId, msg.sender);")
    w(la, "        if (reward == 0) revert VS_NoReward();")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.totalStakedWei + reward > p.capWei) revert VS_CapExceeded();")
    w(la, "        pos.principalWei += reward;")
    w(la, "        pos.rewardDebt = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        p.totalStakedWei += reward;")
    w(la, "        pos.unlockAt = uint64(block.timestamp + p.lockSeconds);")
    w(la, "        totalRewardMinted += reward;")
    w(la, "        emit Compounded(msg.sender, poolId, reward);")
    w(la, "    }")
    w(la, "")


def emit_internal_core(la: list[str]) -> None:
    w(la, "    function _deposit(uint256 poolId, address staker, uint256 amount, bool isNative) internal {")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.phase != VoloPoolPhase.Live) revert VS_PoolClosed();")
    w(la, "        if (isNative && p.assetKind != VoloAssetKind.Native) revert VS_NativeOnly();")
    w(la, "        if (!isNative && p.assetKind != VoloAssetKind.Erc20) revert VS_TokenOnly();")
    w(la, "        if (amount < p.minDepositWei) revert VS_BelowMin();")
    w(la, "        if (p.maxDepositWei != 0 && amount > p.maxDepositWei) revert VS_AboveMax();")
    w(la, "        if (p.totalStakedWei + amount > p.capWei) revert VS_CapExceeded();")
    w(la, "        _accruePool(poolId);")
    w(la, "        VoloPosition storage pos = positions[poolId][staker];")
    w(la, "        if (!pos.exists) {")
    w(la, "            pos.exists = true;")
    w(la, "            pos.epochJoined = uint32(globalEpoch);")
    w(la, "            pos.rewardDebt = 0;")
    w(la, "        } else {")
    w(la, "            pos.rewardDebt = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        }")
    w(la, "        pos.principalWei += amount;")
    w(la, "        pos.rewardDebt = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        pos.unlockAt = uint64(block.timestamp + p.lockSeconds);")
    w(la, "        pos.lastTouch = uint64(block.timestamp);")
    w(la, "        p.totalStakedWei += amount;")
    w(la, "        if (isNative) totalNativeHeld += amount;")
    w(la, "        stakerLaneMask[staker] |= (uint256(1) << (poolId % 256));")
    w(la, "        emit Topped(staker, poolId, amount, pos.unlockAt);")
    w(la, "    }")
    w(la, "")
    w(la, "    function _accruePool(uint256 poolId) internal {")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        if (p.totalStakedWei == 0) {")
    w(la, "            p.lastAccrualTs = uint256(block.timestamp);")
    w(la, "            return;")
    w(la, "        }")
    w(la, "        uint256 elapsed = block.timestamp - p.lastAccrualTs;")
    w(la, "        if (elapsed == 0) return;")
    w(la, "        uint256 increment = VoloMath.mulDivDown(")
    w(la, "            p.totalStakedWei * elapsed * p.rewardBpsAnnual,")
    w(la, "            1,")
    w(la, "            VOLO_YEAR * VOLO_BPS")
    w(la, "        );")
    w(la, "        p.rewardAccPerShare += VoloMath.mulDivDown(increment, 1e18, p.totalStakedWei);")
    w(la, "        p.lastAccrualTs = block.timestamp;")
    w(la, "    }")
    w(la, "")
    w(la, "    function _pendingReward(uint256 poolId, address staker) internal view returns (uint256) {")
    w(la, "        VoloPoolLine storage p = pools[poolId];")
    w(la, "        VoloPosition storage pos = positions[poolId][staker];")
    w(la, "        if (!pos.exists) return 0;")
    w(la, "        uint256 accumulated = VoloMath.mulDivDown(pos.principalWei, p.rewardAccPerShare, 1e18);")
    w(la, "        if (accumulated <= pos.rewardDebt) return 0;")
    w(la, "        return accumulated - pos.rewardDebt;")
    w(la, "    }")
    w(la, "")
    w(la, "    function _pushNative(address to, uint256 amt) internal {")
    w(la, "        if (address(this).balance < amt) revert VS_InsufficientReward();")
    w(la, "        (bool ok, ) = to.call{value: amt}(\"\");")
    w(la, "        if (!ok) revert VS_LaneFault_24();")
    w(la, "    }")
    w(la, "")
    w(la, "    function fundNativeRewards() external payable whenDeskLive {")
    w(la, "        if (msg.value == 0) revert VS_ZeroAmt();")
    w(la, "        emit Pulse_0(lineNonce, msg.sender, msg.value);")
    w(la, "        unchecked { lineNonce += 1; }")
    w(la, "    }")
    w(la, "")
    w(la, "    function fundTokenRewards(uint256 amount) external nonReentrant whenDeskLive {")
    w(la, "        if (amount == 0) revert VS_ZeroAmt();")
    w(la, "        if (address(stakeToken) == address(0)) revert VS_TokenUnset();")
    w(la, "        VoloSafeERC20.safeTransferFrom(stakeToken, msg.sender, address(this), amount);")
    w(la, "        emit Pulse_1(lineNonce, msg.sender, amount);")
    w(la, "        unchecked { lineNonce += 1; }")
    w(la, "    }")
    w(la, "")
    w(la, "    function _aggregateStaked() internal view returns (uint256 sum) {")
    w(la, f"        for (uint256 i = 1; i <= {POOL_COUNT}; ++i) {{")
    w(la, "            sum += pools[i].totalStakedWei;")
    w(la, "        }")
    w(la, "    }")
    w(la, "")
    w(la, "    function _seedEpoch(uint256 epochId) internal {")
    w(la, "        VoloEpochCell storage e = epochs[epochId];")
    w(la, "        e.startedAt = uint64(block.timestamp);")
    w(la, "        e.weightSum = _aggregateStaked();")
    w(la, "        (e.mixHA, e.mixHB) = _splitDigest(epochId, e.weightSum);")
    w(la, "    }")
    w(la, "")
    w(la, "    function _splitDigest(uint256 epochId, uint256 weight) internal view returns (bytes32 hA, bytes32 hB) {")
    w(la, "        hA = keccak256(abi.encode(epochId, weight, ADDRESS_A, _SALT_0));")
    w(la, "        hB = keccak256(abi.encode(weight, epochId, ADDRESS_B, _SALT_1));")
    w(la, "    }")
    w(la, "")
    w(la, "    function laneDigest(uint256 poolId, address staker) public view returns (bytes32) {")
    w(la, "        (bytes32 hA, bytes32 hB) = _splitDigest(poolId, uint256(uint160(staker)));")
    w(la, "        return keccak256(abi.encodePacked(hA, hB, ADDRESS_C, _SALT_2));")
    w(la, "    }")
    w(la, "")


def emit_bootstrap(la: list[str]) -> None:
    w(la, "    function _bootstrapPools() internal {")
    locks = [
        "7 days", "14 days", "30 days", "60 days", "90 days", "120 days", "180 days", "365 days",
    ]
    bps_list = [120, 180, 240, 310, 380, 450, 520, 600, 90, 150, 220, 290, 360, 430]
    mins = [
        "0.01 ether", "0.02 ether", "0.05 ether", "0.1 ether", "0.25 ether", "0.5 ether",
        "1 ether", "2 ether", "0.005 ether", "0.03 ether", "0.08 ether", "0.15 ether",
        "0.4 ether", "0.75 ether",
    ]
    for pid in range(1, POOL_COUNT + 1):
        kind = "Native" if pid % 2 == 1 else "Erc20"
        lock = locks[(pid - 1) % len(locks)]
        bps = bps_list[(pid - 1) % len(bps_list)]
        mn = mins[(pid - 1) % len(mins)]
        cap = f"{pid * 37 + 11} ether"
        maxdep = f"{pid % 7 + 1} ether" if pid % 3 != 0 else "0"
        tag = HEX32[pid % len(HEX32)]
        w(la, f"        pools[{pid}] = VoloPoolLine({{")
        w(la, f"            assetKind: VoloAssetKind.{kind},")
        w(la, "            phase: VoloPoolPhase.Live,")
        w(la, f"            lockSeconds: uint64({lock}),")
        w(la, "            openedAt: uint64(block.timestamp),")
        w(la, f"            rewardBpsAnnual: {bps},")
        w(la, f"            minDepositWei: {mn},")
        w(la, f"            maxDepositWei: {maxdep},")
        w(la, f"            capWei: {cap},")
        w(la, "            totalStakedWei: 0,")
        w(la, "            rewardAccPerShare: 0,")
        w(la, "            lastAccrualTs: block.timestamp,")
        w(la, f"            laneTag: {tag}")
        w(la, "        });")
        w(la, f"        emit Opened({pid}, uint8(VoloAssetKind.{kind}), uint64({lock}), {bps});")
    w(la, "    }")
    w(la, "")


def emit_views(la: list[str]) -> None:
    w(la, "  // ── indexed readers (generated lanes) ─────────────────────────────────")
    # fix indentation - use 4 spaces consistently
    la[-1] = "    // ── indexed readers (generated lanes) ─────────────────────────────────"
    for n in range(VIEW_BATCH):
        w(la, f"    function peekLane_{n}(uint256 poolId, address staker) external view returns (")
        w(la, "        uint256 principal,")
        w(la, "        uint256 pending,")
        w(la, "        uint64 unlockAt,")
        w(la, "        bytes32 digest")
        w(la, "    ) {")
        w(la, "        VoloPosition storage pos = positions[poolId][staker];")
        w(la, "        principal = pos.principalWei;")
        w(la, "        pending = _pendingReward(poolId, staker);")
        w(la, "        unlockAt = pos.unlockAt;")
        w(la, f"        digest = keccak256(abi.encode(poolId, staker, pending, _SALT_{n % len(HEX32)}));")
        w(la, "    }")
        w(la, "")
    for n in range(18):
        w(la, f"    function poolSnapshot_{n}(uint256 poolId) external view returns (")
        w(la, "        uint256 staked,")
        w(la, "        uint256 accPerShare,")
        w(la, "        uint256 bps,")
        w(la, "        uint8 phaseRaw")
        w(la, "    ) {")
        w(la, "        VoloPoolLine storage p = pools[poolId];")
        w(la, "        staked = p.totalStakedWei;")
        w(la, "        accPerShare = p.rewardAccPerShare;")
