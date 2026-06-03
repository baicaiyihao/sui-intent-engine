#[test_only]
module sui_intent_fee::protocol_fee_tests;

use sui::coin;
use sui::sui::SUI;
use sui::test_scenario as ts;
use sui_intent_fee::protocol_fee;

const ADMIN: address = @0xAD;
const USER: address = @0xBEEF;
const ATTACKER: address = @0xBAD;
const FEE: u64 = 5_000_000; // 0.005 SUI

#[test]
fun test_init_creates_treasury_with_default_fee() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(ADMIN);
    let treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
    assert!(protocol_fee::fee_per_intent(&treasury) == 5_000_000, 0);
    assert!(protocol_fee::admin(&treasury) == ADMIN, 0);
    assert!(protocol_fee::balance(&treasury) == 0, 0);
    assert!(protocol_fee::intent_count(&treasury) == 0, 0);
    assert!(protocol_fee::total_collected(&treasury) == 0, 0);
    ts::return_shared(treasury);
    ts::end(sc);
}

#[test]
fun test_pay_fee_exact_amount() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        let coin = coin::mint_for_testing<SUI>(FEE, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
        assert!(protocol_fee::balance(&treasury) == FEE, 0);
        assert!(protocol_fee::total_collected(&treasury) == FEE, 0);
        assert!(protocol_fee::intent_count(&treasury) == 1, 0);
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
fun test_pay_fee_with_change_returned() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        // User overpays by 0.01 SUI; should get 0.01 back
        let overpay = FEE + 10_000_000;
        let coin = coin::mint_for_testing<SUI>(overpay, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"analysis", ts::ctx(&mut sc));
        // Treasury should hold exactly FEE
        assert!(protocol_fee::balance(&treasury) == FEE, 0);
        ts::return_shared(treasury);
    };
    // Advance tx to flush inventory, then verify USER got the change back
    sc.next_tx(USER);
    let change_coin = ts::take_from_address<coin::Coin<SUI>>(&sc, USER);
    assert!(coin::value(&change_coin) == 10_000_000, 0);
    ts::return_to_address(USER, change_coin);
    ts::end(sc);
}

#[test]
fun test_multiple_payments_accumulate() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        // 3 payments
        let mut i = 0;
        while (i < 3) {
            let coin = coin::mint_for_testing<SUI>(FEE, ts::ctx(&mut sc));
            protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
            i = i + 1;
        };
        assert!(protocol_fee::balance(&treasury) == FEE * 3, 0);
        assert!(protocol_fee::intent_count(&treasury) == 3, 0);
        assert!(protocol_fee::total_collected(&treasury) == FEE * 3, 0);
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
#[expected_failure(abort_code = protocol_fee::EInsufficientPayment)]
fun test_underpay_fails() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        // Pay only half the fee
        let coin = coin::mint_for_testing<SUI>(FEE / 2, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
fun test_admin_can_withdraw() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    // User pays first
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        let coin = coin::mint_for_testing<SUI>(FEE, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    // Admin withdraws
    sc.next_tx(ADMIN);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::withdraw_all(&mut treasury, ts::ctx(&mut sc));
        assert!(protocol_fee::balance(&treasury) == 0, 0);
        ts::return_shared(treasury);
    };
    // Advance tx to flush inventory, then verify ADMIN got the Coin<SUI>
    sc.next_tx(ADMIN);
    let admin_coin = ts::take_from_address<coin::Coin<SUI>>(&sc, ADMIN);
    assert!(coin::value(&admin_coin) == FEE, 0);
    ts::return_to_address(ADMIN, admin_coin);
    ts::end(sc);
}

#[test]
#[expected_failure(abort_code = protocol_fee::ENotAdmin)]
fun test_non_admin_cannot_withdraw() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        let coin = coin::mint_for_testing<SUI>(FEE, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    // Attacker tries to withdraw
    sc.next_tx(ATTACKER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::withdraw_all(&mut treasury, ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
fun test_admin_can_update_fee() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(ADMIN);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::set_fee(&mut treasury, 10_000_000, ts::ctx(&mut sc));
        assert!(protocol_fee::fee_per_intent(&treasury) == 10_000_000, 0);
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
#[expected_failure(abort_code = protocol_fee::EZeroFeeNotAllowed)]
fun test_cannot_set_zero_fee() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(ADMIN);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::set_fee(&mut treasury, 0, ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
fun test_admin_role_can_be_transferred() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(ADMIN);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::transfer_admin(&mut treasury, USER, ts::ctx(&mut sc));
        assert!(protocol_fee::admin(&treasury) == USER, 0);
        ts::return_shared(treasury);
    };
    // New admin can now withdraw
    sc.next_tx(USER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        // No funds yet, but admin check should pass
        let coin = coin::mint_for_testing<SUI>(FEE, ts::ctx(&mut sc));
        protocol_fee::pay_fee(&mut treasury, coin, b"trade", ts::ctx(&mut sc));
        protocol_fee::withdraw_all(&mut treasury, ts::ctx(&mut sc));
        assert!(protocol_fee::balance(&treasury) == 0, 0);
        ts::return_shared(treasury);
    };
    ts::end(sc);
}

#[test]
#[expected_failure(abort_code = protocol_fee::ENotAdmin)]
fun test_non_admin_cannot_set_fee() {
    let mut sc = ts::begin(ADMIN);
    {
        protocol_fee::init_for_testing(ts::ctx(&mut sc));
    };
    sc.next_tx(ATTACKER);
    {
        let mut treasury = ts::take_shared<protocol_fee::ProtocolTreasury>(&sc);
        protocol_fee::set_fee(&mut treasury, 999_999_999, ts::ctx(&mut sc));
        ts::return_shared(treasury);
    };
    ts::end(sc);
}
