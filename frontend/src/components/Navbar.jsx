import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

export const Navbar = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        navigate("/", { replace: true });
        await logout();
    };

    return (
        <header
            data-testid="site-navbar"
            className="sticky top-0 z-40 w-full border-b border-white/10 bg-black/60 backdrop-blur-xl"
        >
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
                <Link
                    to="/"
                    data-testid="nav-logo"
                    className="flex items-center gap-2 transition-colors duration-200 hover:text-ember-500"
                >
                    <span className="grid h-8 w-8 place-items-center rounded-md bg-ember-500 font-serif text-lg font-semibold text-black">
                        W
                    </span>
                    <span className="font-serif text-xl tracking-tight">
                        WeAre <span className="text-ember-500">Creators</span>
                    </span>
                </Link>

                <nav className="hidden items-center gap-8 md:flex">
                    <a
                        href="#creators"
                        data-testid="nav-creators"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        For Creators
                    </a>
                    <a
                        href="#brands"
                        data-testid="nav-brands"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        For Brands
                    </a>
                    <a
                        href="#how"
                        data-testid="nav-how"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        How it works
                    </a>
                </nav>

                <div className="flex items-center gap-3">
                    {user && user !== false ? (
                        <>
                            <Link
                                to="/dashboard"
                                data-testid="nav-dashboard"
                                className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                            >
                                Dashboard
                            </Link>
                            <Button
                                data-testid="nav-logout-btn"
                                onClick={handleLogout}
                                variant="outline"
                                className="border-white/15 bg-transparent text-foreground hover:bg-white/5"
                            >
                                Log out
                            </Button>
                        </>
                    ) : (
                        <>
                            <Link
                                to="/login"
                                data-testid="nav-login-link"
                                className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                            >
                                Log in
                            </Link>
                            <Link to="/signup" data-testid="nav-signup-link">
                                <Button className="rounded-full bg-ember-500 px-5 text-black hover:bg-ember-400">
                                    Join waitlist
                                </Button>
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
};
