import { Link } from "react-router-dom";
import { motion } from "motion/react";

import { HeaderUserMenu } from "./HeaderUserMenu";

export function Header() {
    return (
        <motion.header
            initial={{ y: -100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60"
        >
            <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
                <div className="flex items-center gap-6">
                    <Link to="/" className="flex items-center space-x-2">
                        <motion.div
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="bg-foreground text-background font-bold px-2 py-1 rounded-md text-sm tracking-widest uppercase transition-colors"
                        >
                            Monolith
                        </motion.div>
                    </Link>

                    <nav className="hidden md:flex gap-6">
                        <motion.div whileHover={{ y: -1 }}>
                            <Link
                                to="/dashboard"
                                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                            >
                                Dashboard
                            </Link>
                        </motion.div>
                    </nav>
                </div>

                <div className="flex items-center gap-4">
                    <motion.div className="md:hidden" whileHover={{ y: -1 }}>
                        <Link
                            to="/dashboard"
                            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                        >
                            Dashboard
                        </Link>
                    </motion.div>

                    <HeaderUserMenu />
                </div>
            </div>
        </motion.header>
    );
}
