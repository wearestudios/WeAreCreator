// The graph, as links.
//
// An admin tracing a problem goes creator → campaign → brand → another campaign
// without ever wanting a list in between. That only works if every name is a
// link everywhere it appears, which in turn only works if there is one way to
// render a name — otherwise the twentieth place forgets.
//
// Each of these renders plain text when there is no id, rather than a link to
// nowhere. A row whose brand was deleted should read as a name, not as a
// promise that 404s.
import React from "react";
import { Link } from "react-router-dom";

const CLASS =
    "transition-colors duration-150 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm";

function EntityLink({ to, id, children, className = "", testid, fallback }) {
    const label = children || fallback || "—";
    if (!id) {
        return (
            <span data-testid={testid} className={className}>
                {label}
            </span>
        );
    }
    return (
        <Link to={to} data-testid={testid} className={`${CLASS} ${className}`}>
            {label}
        </Link>
    );
}

export const CreatorLink = ({ id, name, className, testid }) => (
    <EntityLink
        to={`/admin/creators/${id}`}
        id={id}
        className={className}
        testid={testid}
        fallback="Unknown creator"
    >
        {name}
    </EntityLink>
);

export const BrandLink = ({ id, name, className, testid }) => (
    <EntityLink
        to={`/admin/brands/${id}`}
        id={id}
        className={className}
        testid={testid}
        fallback="Unknown brand"
    >
        {name}
    </EntityLink>
);

export const CampaignLink = ({ id, title, className, testid }) => (
    <EntityLink
        to={`/admin/campaigns/${id}`}
        id={id}
        className={className}
        testid={testid}
        fallback="Untitled campaign"
    >
        {title}
    </EntityLink>
);

export const CollaborationLink = ({ id, children, className, testid }) => (
    <EntityLink
        to={`/admin/collaborations/${id}`}
        id={id}
        className={className}
        testid={testid}
        fallback="Application"
    >
        {children}
    </EntityLink>
);
