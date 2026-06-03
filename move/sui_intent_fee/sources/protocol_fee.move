/// ProtocolFee - SUI Intent Engine on-chain fee collector
///
/// One shared `ProtocolTreasury` is created at `init()`. Users call
/// `pay_fee` as the first step of their trade PTB, then continue with
/// the rest of the intent execution. The admin (deployer by default)
/// can withdraw accumulated fees and adjust the per-intent fee amount.
///
/// Events are emitted on every action so the activity is fully auditable
/// on-chain (and indexable by a future explorer / dashboard).
module sui_intent_fee::protocol_fee;

use sui::balance::{Self, Balance};
use sui::coin::{Self, Coin};
use sui::event;
use sui::object::{Self, UID};
use sui::sui::SUI;
use sui::transfer;
use sui::tx_context::{Self, TxContext};

// ===== Errors =====
const EInsufficientPayment: u64 = 0;
const ENotAdmin: u64 = 1;
const EZeroFeeNotAllowed: u64 = 2;

// ===== Constants =====
// Default fee: 0.005 SUI (5_000_000 MIST) per intent
//   - Low enough to not deter users (~$0.0015 at SUI=$0.30)
//   - High enough to accumulate (1 SUI / 200 intents)
// Admin can change via `set_fee` after deploy.
const DEFAULT_FEE_MIST: u64 = 5_000_000;

// ===== Objects =====

/// Shared treasury that accumulates SUI fees from every intent.
public struct ProtocolTreasury has key, store {
    id: UID,
    /// SUI balance of all collected fees
    balance: Balance<SUI>,
    /// Lifetime total collected (in MIST), for stats / dashboards
    total_collected: u64,
    /// Number of intents paid for, for stats / dashboards
    intent_count: u64,
    /// Address allowed to call admin functions
    admin: address,
    /// Current fee amount (MIST) charged per `pay_fee` call
    fee_per_intent: u64,
}

// ===== Events =====

public struct FeePaid has copy, drop {
    treasury: ID,
    payer: address,
    amount: u64,
    /// Free-form tag the caller passes (e.g. b"trade", b"analysis")
    intent_type: vector<u8>,
    intent_number: u64,
}

public struct FeeWithdrawn has copy, drop {
    treasury: ID,
    admin: address,
    amount: u64,
}

public struct FeeUpdated has copy, drop {
    treasury: ID,
    admin: address,
    old_fee: u64,
    new_fee: u64,
}

public struct AdminTransferred has copy, drop {
    treasury: ID,
    old_admin: address,
    new_admin: address,
}

// ===== Init =====

/// Module initializer — called once at publish time.
/// Creates and shares the ProtocolTreasury, transfers admin to publisher.
fun init(ctx: &mut TxContext) {
    let treasury = ProtocolTreasury {
        id: object::new(ctx),
        balance: balance::zero(),
        total_collected: 0,
        intent_count: 0,
        admin: tx_context::sender(ctx),
        fee_per_intent: DEFAULT_FEE_MIST,
    };
    transfer::share_object(treasury);
}

// ===== User-facing =====

/// Pay the protocol fee for one intent. Returns any change to the sender.
///
/// Typical usage in a PTB:
///   1. `coin::split(gas_coin, fee_amount, ctx)` → fee_coin
///   2. `protocol_fee::pay_fee(treasury, fee_coin, b"trade", ctx)` (no return value needed)
///   3. Continue with the rest of the intent PTB
public fun pay_fee(
    treasury: &mut ProtocolTreasury,
    mut payment: Coin<SUI>,
    intent_type: vector<u8>,
    ctx: &mut TxContext,
) {
    let required = treasury.fee_per_intent;
    let paid = coin::value(&payment);
    assert!(paid >= required, EInsufficientPayment);

    // Split out the fee, return the change
    let change = coin::split(&mut payment, required, ctx);
    coin::put(&mut treasury.balance, change);

    // Update stats
    treasury.total_collected = treasury.total_collected + required;
    treasury.intent_count = treasury.intent_count + 1;

    // Emit event for on-chain audit
    event::emit(FeePaid {
        treasury: object::id(treasury),
        payer: tx_context::sender(ctx),
        amount: required,
        intent_type,
        intent_number: treasury.intent_count,
    });

    // Return change (or original coin if paid == required)
    transfer::public_transfer(payment, tx_context::sender(ctx));
}

// ===== Admin =====

/// Withdraw all accumulated SUI to the admin address.
public fun withdraw_all(
    treasury: &mut ProtocolTreasury,
    ctx: &mut TxContext,
) {
    let admin = tx_context::sender(ctx);
    assert!(admin == treasury.admin, ENotAdmin);
    let amount = balance::value(&treasury.balance);
    assert!(amount > 0, EInsufficientPayment);
    let coin = coin::take(&mut treasury.balance, amount, ctx);
    event::emit(FeeWithdrawn {
        treasury: object::id(treasury),
        admin,
        amount,
    });
    transfer::public_transfer(coin, admin);
}

/// Update the per-intent fee. Must be > 0.
public fun set_fee(
    treasury: &mut ProtocolTreasury,
    new_fee: u64,
    ctx: &mut TxContext,
) {
    let admin = tx_context::sender(ctx);
    assert!(admin == treasury.admin, ENotAdmin);
    assert!(new_fee > 0, EZeroFeeNotAllowed);
    let old_fee = treasury.fee_per_intent;
    treasury.fee_per_intent = new_fee;
    event::emit(FeeUpdated {
        treasury: object::id(treasury),
        admin,
        old_fee,
        new_fee,
    });
}

/// Transfer admin role. Useful for treasury management handover.
public fun transfer_admin(
    treasury: &mut ProtocolTreasury,
    new_admin: address,
    ctx: &mut TxContext,
) {
    let admin = tx_context::sender(ctx);
    assert!(admin == treasury.admin, ENotAdmin);
    let old_admin = treasury.admin;
    treasury.admin = new_admin;
    event::emit(AdminTransferred {
        treasury: object::id(treasury),
        old_admin,
        new_admin,
    });
}

// ===== View functions =====

public fun fee_per_intent(treasury: &ProtocolTreasury): u64 { treasury.fee_per_intent }
public fun total_collected(treasury: &ProtocolTreasury): u64 { treasury.total_collected }
public fun intent_count(treasury: &ProtocolTreasury): u64 { treasury.intent_count }
public fun balance(treasury: &ProtocolTreasury): u64 { balance::value(&treasury.balance) }
public fun admin(treasury: &ProtocolTreasury): address { treasury.admin }

// ===== Test helpers =====
#[test_only]
public fun init_for_testing(ctx: &mut TxContext) {
    init(ctx)
}

#[test_only]
public fun new_treasury_for_testing(
    admin: address,
    fee: u64,
    ctx: &mut TxContext,
): ProtocolTreasury {
    ProtocolTreasury {
        id: object::new(ctx),
        balance: balance::zero(),
        total_collected: 0,
        intent_count: 0,
        admin,
        fee_per_intent: fee,
    }
}
