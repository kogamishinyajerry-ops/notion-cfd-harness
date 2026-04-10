import { Outlet } from 'react-router-dom';

function App() {
  return (
    <>
      <nav>
        <a href="/">Dashboard</a>
        <a href="/cases">Cases</a>
        <a href="/jobs">Jobs</a>
        <a href="/reports">Reports</a>
        <a href="/settings">Settings</a>
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  );
}

export default App;
