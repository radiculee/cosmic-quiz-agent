import { Link } from "../components/Link";
import { PATHS, usePageTitle } from "../router";

/** Any address the app does not know. */
export function NotFoundPage() {
  usePageTitle("Not found");
  return (
    <div className="flex flex-col items-center pt-16 text-center">
      <p className="on-scene-muted font-pixel text-[9px] uppercase">404</p>
      <h1 className="on-scene mt-4 font-heading text-4xl font-bold">Nothing at this address</h1>
      <p className="on-scene mt-4">
        <Link to={PATHS.home} className="text-teal underline underline-offset-4 hover:text-ink">
          Back to the start
        </Link>
      </p>
    </div>
  );
}
