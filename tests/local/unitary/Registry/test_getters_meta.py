import itertools
import pytest
from scripts.utils import pack_values

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@pytest.fixture(scope="module", autouse=True)
def registry(
    Registry,
    gauge_controller,
    alice,
    swap,
    meta_swap,
    lp_token,
    meta_lp_token,
    n_coins,
    n_metacoins,
    is_v1,
    underlying_decimals,
    meta_decimals,
):
    registry = Registry.deploy(gauge_controller, {"from": alice})
    registry.add_pool_without_underlying(
        swap,
        n_coins,
        lp_token,
        "0x00",
        pack_values(underlying_decimals),
        0,  # use rates
        hasattr(swap, "initial_A"),
        is_v1,
        {"from": alice},
    )
    registry.add_metapool(
        meta_swap, n_metacoins, meta_lp_token, pack_values(meta_decimals), {"from": alice}
    )
    yield registry


def test_find_pool(registry, meta_swap, meta_coins, underlying_coins, n_metacoins, lp_token):
    for i, j in itertools.combinations(range(n_metacoins), 2):
        assert registry.find_pool_for_coins(meta_coins[i], meta_coins[j]) == meta_swap

    for meta, base in itertools.product(meta_coins[:-1], underlying_coins):
        assert registry.find_pool_for_coins(meta, base) == meta_swap


def test_find_pool_not_exists(registry, meta_swap, meta_coins, underlying_coins, n_coins):
    for i in range(n_coins):
        assert registry.find_pool_for_coins(meta_coins[i], meta_coins[i]) == ZERO_ADDRESS
        assert registry.find_pool_for_coins(underlying_coins[i], underlying_coins[i]) == ZERO_ADDRESS


def test_get_n_coins(registry, meta_swap, n_coins, n_metacoins):
    assert registry.get_n_coins(meta_swap) == [n_metacoins, n_coins + n_metacoins - 1]


def test_get_coins(registry, meta_swap, meta_coins, n_metacoins):
    assert registry.get_coins(meta_swap) == meta_coins + [ZERO_ADDRESS] * (8 - n_metacoins)


def test_get_underlying_coins(registry, meta_swap, meta_coins, underlying_coins):
    expected = meta_coins[:-1] + underlying_coins
    expected += [ZERO_ADDRESS] * (8 - len(expected))
    assert registry.get_underlying_coins(meta_swap) == expected


def test_get_decimals(registry, meta_swap, meta_decimals, n_metacoins):
    expected = meta_decimals + [0] * (8 - n_metacoins)
    assert registry.get_decimals(meta_swap) == expected
    assert registry.get_pool_info(meta_swap)["decimals"] == expected


def test_get_underlying_decimals(registry, meta_swap, meta_decimals, underlying_decimals):
    expected = meta_decimals[:-1] + underlying_decimals
    expected += [0] * (8 - len(expected))
    assert registry.get_underlying_decimals(meta_swap) == expected
    assert registry.get_pool_info(meta_swap)["underlying_decimals"] == expected


def test_get_pool_coins(
    registry,
    meta_swap,
    meta_coins,
    underlying_coins,
    meta_decimals,
    underlying_decimals,
    n_metacoins,
    n_coins,
):
    coin_info = registry.get_pool_coins(meta_swap)
    ul_trailing = 9 - n_coins - n_metacoins
    assert coin_info["coins"] == meta_coins + [ZERO_ADDRESS] * (8 - n_metacoins)
    assert coin_info["underlying_coins"] == meta_coins[:-1] + underlying_coins + [ZERO_ADDRESS] * ul_trailing
    assert coin_info["decimals"] == meta_decimals + [0] * (8 - n_metacoins)
    assert coin_info["underlying_decimals"] == meta_decimals[:-1] + underlying_decimals + [0] * ul_trailing


def test_get_rates(alice, registry, meta_swap, swap, n_metacoins):
    swap._set_virtual_price(12345678, {"from": alice})
    expected = [10 ** 18] * (n_metacoins - 1) + [12345678] + [0] * (8 - n_metacoins)
    assert registry.get_rates(meta_swap) == expected
    assert registry.get_pool_info(meta_swap)["rates"] == expected


def test_get_balances(registry, meta_swap, n_metacoins):
    balances = [1234, 2345, 3456, 4567]
    meta_swap._set_balances(balances)

    expected = balances[:n_metacoins] + [0] * (8 - n_metacoins)
    assert registry.get_balances(meta_swap) == expected
    assert registry.get_pool_info(meta_swap)["balances"] == expected


def test_get_underlying_balances(alice, registry, swap, meta_swap, n_metacoins, n_coins, lp_token):
    balances = [1234, 2345, 3456, 4567]
    meta_swap._set_balances(balances)

    lp_token._mint_for_testing(alice, balances[n_metacoins - 1] * 5)

    underlying_balances = [5678, 6789, 7890, 8901]
    swap._set_balances(underlying_balances)

    expected = balances[: n_metacoins - 1] + [i // 5 for i in underlying_balances[:n_coins]]
    expected += [0] * (8 - len(expected))

    assert registry.get_underlying_balances(meta_swap) == expected
    assert registry.get_pool_info(meta_swap)["underlying_balances"] == expected


def test_get_admin_balances(alice, registry, meta_swap, meta_coins):
    assert registry.get_admin_balances(meta_swap) == [0] * 8

    expected = [0] * 8
    for i, coin in enumerate(meta_coins, start=1):
        expected[i - 1] = 666 * i
        coin._mint_for_testing(meta_swap, expected[i - 1])

    assert registry.get_admin_balances(meta_swap) == expected

    meta_swap._set_balances([i // 4 for i in expected[:4]])

    expected = [i - i // 4 for i in expected]
    assert registry.get_admin_balances(meta_swap) == expected


def test_get_coin_indices(
    alice, registry, meta_swap, underlying_coins, meta_coins, n_coins, n_metacoins
):
    for i, j in itertools.combinations(range(n_metacoins), 2):
        assert registry.get_coin_indices(meta_swap, meta_coins[i], meta_coins[j]) == (i, j, False)

    coins = meta_coins[:-1] + underlying_coins
    for i, j in itertools.product(range(n_coins - 1), range(n_coins, n_coins + n_metacoins - 1)):
        assert registry.get_coin_indices(meta_swap, coins[i], coins[j]) == (i, j, True)


@pytest.mark.once
def test_get_A(alice, registry, meta_swap):
    assert registry.get_A(meta_swap) == meta_swap.A()

    meta_swap._set_A(12345, 0, 0, 0, 0, {"from": alice})
    assert registry.get_A(meta_swap) == 12345


@pytest.mark.once
def test_get_fees(alice, registry, meta_swap):
    assert registry.get_fees(meta_swap) == [meta_swap.fee(), meta_swap.admin_fee()]

    meta_swap._set_fees_and_owner(12345, 31337, 0, 0, alice, {"from": alice})
    assert registry.get_fees(meta_swap) == [12345, 31337]


@pytest.mark.once
def test_get_virtual_price_from_lp_token(alice, registry, meta_swap, meta_lp_token):
    assert registry.get_virtual_price_from_lp_token(meta_lp_token) == 10 ** 18
    meta_swap._set_virtual_price(12345678, {"from": alice})
    assert registry.get_virtual_price_from_lp_token(meta_lp_token) == 12345678


@pytest.mark.once
def test_get_pool_from_lp_token(registry, swap, meta_swap, lp_token, meta_lp_token):
    assert registry.get_pool_from_lp_token(meta_lp_token) == meta_swap
    assert registry.get_pool_from_lp_token(lp_token) == swap


@pytest.mark.once
def test_get_lp_token(registry, swap, meta_swap, lp_token, meta_lp_token):
    assert registry.get_lp_token(meta_swap) == meta_lp_token
    assert registry.get_lp_token(swap) == lp_token
