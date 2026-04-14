from pithy.html import (
    Button,
    Div,
    Html,
    Input,
    Main,
    P,
    Script,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)
from pithy.web.app import WebApp
from pithy.web.request import Request
from pithy.web.response import Response


def full_page_basic():
    "Html document skeleton common to all pages, including unauthenticated pages."

    html = Html.doc(title="Cheesesteak Club Members DB")
    head = html.head
    head.append(
        Script(
            src="https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta1/dist/htmx.min.js",
            defer="",
        )
    )
    body = html.body
    header = body.header
    header.append("Cheesesteak Club Members DB")

    return html


members = [
    (1, "Pat Olivieri",   51,    "1930-01-01"),
    (2, "Geno Vento",     35,    "1966-03-15"),
    (3, "Carmen DiNardo",  24,   "1971-07-04"),
    (4, "Rosa Sabatino",    5,  "1985-09-22"),
    (5, "Frankie Abbate",  11,   "1993-11-10"),
]


def find_member(member_id: int):
    for m in members:
        if m[0] == member_id:
            return m
    return None


class MaxTestApp(WebApp):
    def info_table(self):
        thead = Thead(Tr(Th("ID"), Th("Name"), Th("Cheesesteaks Eaten"), Th("Member Since")))
        tbody = Tbody()
        for member_id, name, cs_eaten, since in members:
            tbody.append(Tr(Td(str(member_id)), Td(name), Td(str(cs_eaten)), Td(since), hx_trigger="click", hx_swap="outerHTML", hx_get=f"/member/{member_id}", id=member_id))
        return Div(Table(thead, tbody))

    def edit_row_htmx(self, request: Request) -> Response:
      member_id = int(request.path[len("/member/"):])
      _, name, cs_eaten, since = find_member(member_id)

      save_button = Button("Save", hx_trigger="click", hx_target="closest tr", hx_swap="outerHTML", hx_post=f"/member/edit/{member_id}", hx_include="closest tr", onclick='event.stopPropagation()')
      delete_button = Button("Delete", hx_trigger="click", hx_target="closest tr", hx_swap="outerHTML", hx_delete=f"/member/{member_id}", onclick='event.stopPropagation()')
      new_row = Tr(Td(str(member_id)), Td(Input(name="name", type="text", value=name)), Td(Input(name="cs_eaten", type="text", value=cs_eaten)), Td(Input(name="since", type="text", value=since)), Td(save_button), Td(delete_button), id=member_id)

      return Response(
            body=new_row,
            media_type="text/html;charset=utf-8",
        )

    def update_members_data(self, member_id: int, name, cs_eaten, since):
      old = find_member(member_id)
      idx = members.index(old)
      members[idx] = (member_id, name or old[1], cs_eaten or old[2], since or old[3])

    def save_row_htmx(self, request: Request) -> Response:
      member_id = int(request.path[len("/member/edit/"):])
      params = request.parse_urlencoded(max_bytes=16_384)
      name = params['name'][0]
      cs_eaten = params['cs_eaten'][0]
      since = params['since'][0]

      self.update_members_data(member_id, name, int(cs_eaten), since)

      new_row = Tr(Td(str(member_id)), Td(name), Td(str(cs_eaten)), Td(since), hx_trigger="click", hx_swap="outerHTML", hx_get=f"/member/{member_id}", id=member_id)

      return Response(
            body=new_row,
            media_type="text/html;charset=utf-8",
        )

    def delete_row_htmx(self, request: Request) -> Response:
      member_id = int(request.path[len("/member/"):])
      members[:] = [m for m in members if m[0] != member_id]
      updated_count = P(f"Click a member to edit. Total current members: {len(members)}", id="count", hx_swap_oob="true")
      return Response(body=updated_count, media_type="text/html;charset=utf-8")

    

    def handle_request(self, request: Request) -> Response:
        if request.method == "GET":
          if request.path.startswith("/member/"):
            return self.edit_row_htmx(request)
          else:
            return self.page()
        elif request.method == "POST":
          if request.path.startswith("/member/edit/"):
            return self.save_row_htmx(request)
        elif request.method == "DELETE":
          if request.path.startswith("/member/"):
            return self.delete_row_htmx(request)

    def page(self) -> Response:
        main = Main(P(f"Click a member to edit. Total current members: {len(members)}", id="count", hx_swap_oob="true"))
        main.append(self.info_table())

        page = full_page_basic()
        page.body.append(main)

        return Response(body=page, media_type="text/html;charset=utf-8")


def main() -> None:
    from .server import WebServer

    app = MaxTestApp()
    server = WebServer(app=app)
    server.serve_forever()


if __name__ == "__main__":
    main()
