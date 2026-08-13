import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/components/NotificationBell";

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
                        href="#how-it-works"
                        data-testid="nav-how"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        How it works
                    </a>
                    <a
                        href="#why"
                        data-testid="nav-why"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        Why WeAre
                    </a>
                    <Link
                        to="/signup?role=brand"
                        data-testid="nav-for-brands"
                        className="text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        For brands →
                    </Link>
                </nav>

                <div className="flex items-center gap-3">
                    {user && user !== false ? (
                        <>
                            {(user.role === "creator" || user.role === "admin") && (
                                <Link
                                    to="/campaigns"
                                    data-testid="nav-campaigns"
                                    className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                                >
                                    Campaigns
                                </Link>
                            )}
                            {user.role === "brand" && (
                                <>
                                    <Link
                                        to="/brand/creators"
                                        data-testid="nav-brand-creators"
                                        className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                                    >
                                        Creators
                                    </Link>
                                    <Link
                                        to="/campaigns/new"
                                        data-testid="nav-post-campaign"
                                        className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                                    >
                                        Post a campaign
                                    </Link>
                                </>
                            )}
                            {user.role === "admin" && (
                                <Link
                                    to="/admin"
                                    data-testid="nav-admin"
                                    className="hidden text-sm text-ember-500 transition-colors duration-200 hover:text-ember-400 sm:inline"
                                >
                                    Admin
                                </Link>
                            )}
                            <Link
                                to="/dashboard"
                                data-testid="nav-dashboard"
                                className="hidden text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground sm:inline"
                            >
                                Dashboard
                            </Link>
                            <NotificationBell />
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
                            <Link
                                to="/signup?role=creator"
                                data-testid="nav-signup-creator-link"
                            >
                                <Button className="rounded-full bg-ember-500 px-5 text-black hover:bg-ember-400">
                                    Sign up as a creator
                                </Button>
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
};
