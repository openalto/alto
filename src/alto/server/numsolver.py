#!/usr/bin/env python3

from cvxopt import solvers, matrix, spdiag, log
import numpy as np
from scipy.optimize import fmin_slsqp, least_squares

def solve_num(A, c, alpha, rho, niter=100, debug=False):
    """
    This function solves the NUM problem.

        max sum(U(x))
           Ax <= c

    The srikant's utility function:
        U(x) = rho * x^(1-alpha) / (1 - alpha)
    """
    B = matrix(A, tc='d')
    c = matrix(c, tc='d')

    alpha = np.array(alpha)
    rho = np.array(rho)

    m, n = B.size

    assert n == len(alpha)
    assert n == len(rho)
    assert m == len(c)

    alphas = 1 - alpha

    def f(x):
        y = np.array(x.T).flatten()
        return sum(np.where(alphas==0,
                            rho*np.log(y),
                            rho*np.power(y, alphas) / (alphas + 1e-9)))

    def fprime(x):
        y = np.array(x.T).flatten()
        return rho * np.power(y, -alpha)

    def fpprime(x, z):
        y = np.array(x.T).flatten()
        return z[0] * rho * -alpha * y**(-alpha-1)

    def F(x=None, z=None):
        if x is None:
            return 0, matrix(1.0, (n, 1))
        if min(x) <= 0.0:
            return None
        fx = matrix(-f(x), (1,1))
        fpx = matrix(-fprime(x), (1, n))
        if z is None:
            return fx, fpx
        fppx = spdiag(matrix(-fpprime(x,z), (n, 1)))
        return fx, fpx, fppx

    ret = solvers.cp(F, G=B, h=c, maxiters=niter, options={'show_progress': debug})
    x, u = ret['x'], ret['zl']
    return np.array(x).flatten(), np.array(u).flatten()

def solve(A, c, alpha, rho, niter=100, debug=False):
    """
    For backward compatibility
    """
    return solve_num(A, c, alpha, rho, niter, debug)

def train(samples, A, c, alpha):
    m, n = A.shape

    def f(rho0):
        rho = np.concatenate((rho0, np.ones(1)))
        x, u = solve_num(A, c, alpha, rho)
        return sum([np.power(x - sample, 2) for sample in samples])

    rho = fmin_slsqp(f, np.zeros(m-1),
                     bounds=[(0, np.inf) for i in range(m-1)],
                     disp=0)
    return rho

if __name__ == '__main__':
    A = np.array([[1, 0, 0], [1, 1, 0], [1, 0, 1]])
    c = np.array([1, 1, 1])
    alpha = np.ones(3)

    samples = [np.array([0.33, 0.67, 0.67])]

    rho = train(samples, A, c, alpha)

    print(rho)
