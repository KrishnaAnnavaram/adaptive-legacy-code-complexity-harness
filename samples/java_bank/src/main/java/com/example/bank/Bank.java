package com.example.bank;

import java.util.HashMap;
import java.util.Map;

/**
 * Coordinates accounts and money movement. This is the call-graph hub: transfer
 * calls withdraw/deposit on Account and records to TransactionLog. Exercises
 * if/else, switch over an enum, try/catch on a custom exception, cross-class calls.
 * Accounts are held in memory (no DB).
 */
public class Bank {

    private final Map<String, Account> accounts = new HashMap<>();
    private final TransactionLog log = new TransactionLog();

    public void addAccount(Account account) {
        accounts.put(account.getId(), account);
    }

    public Account findAccount(String id) {
        return accounts.get(id);
    }

    public boolean transfer(String fromId, String toId, double amount) {
        Account from = findAccount(fromId);
        Account to = findAccount(toId);
        if (from == null || to == null) {
            return false;
        }
        try {
            from.withdraw(amount);
            to.deposit(amount);
            log.record(fromId, toId, new Money(Math.round(amount * 100), "USD"));
            return true;
        } catch (InsufficientFundsException ex) {
            from.audit("TRANSFER_FAILED");
            return false;
        }
    }

    public AccountType classify(Account account) {
        return AccountType.forBalance(account.getBalance());
    }

    public String describe(AccountType type) {
        switch (type) {
            case BASIC:
                return "Basic account";
            case SILVER:
                return "Silver account";
            case GOLD:
                return "Gold account";
            default:
                return "Unknown";
        }
    }
}
