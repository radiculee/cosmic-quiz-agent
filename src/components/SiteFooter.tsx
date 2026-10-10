import { SCENE_CHIP } from "../pages/common";
import { PATHS } from "../router";
import { Link } from "./Link";

/** The foot of every page: the link to what the site keeps about a visitor. */
export function SiteFooter() {
  return (
    <footer className="flex justify-center px-4 pb-8">
      <Link to={PATHS.privacy} className={SCENE_CHIP}>
        Privacy
      </Link>
    </footer>
  );
}
