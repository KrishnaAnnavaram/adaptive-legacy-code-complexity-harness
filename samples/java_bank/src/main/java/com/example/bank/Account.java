package com.example.bank;

import java.util.ArrayList;
import java.util.List;
import com.example.bank.util.Validation;

/**
 * A basic bank account.
 *
 * deposit / withdraw / getBalance all touch {@code balance} -> high cohesion,
 * while the audit trail is a separate responsibility. Exercises: fields,
 * constructor, guard clauses, a custom exception, cross-package static calls.
 */
public class Account implements Auditable {

    private final String id;
    private final String owner;
    protected double balance;
    private final List<String> auditTrail = new ArrayList<>();

    public Account(String id, String owner, double opening) {
        this.id = id;
        this.owner = owner;
        this.balance = opening;
    }

    public void deposit(double amount) {
        Validation.requirePositive(amount);
        balance += amount;
        audit("DEPOSIT");
    }

    public void withdraw(double amount) {
        Validation.requirePositive(amount);
        if (amount > balance) {
            throw new InsufficientFundsException("insufficient funds for " + owner);
        }
        balance -= amount;
        audit("WITHDRAW");
    }

    public double getBalance() {
        return balance;
    }

    public String getId() {
        return id;
    }

    @Override
    public void audit(String event) {
        auditTrail.add(event + ":" + owner);
    }
}
