import SwiftUI

struct MenuItem: Identifiable {
    let id = UUID()
    let name: String
    let price: Double
}

struct ContentView: View {
    private let menuItems = [
        MenuItem(name: "Kaffee", price: 2.5),
        MenuItem(name: "Tee", price: 2.0),
        MenuItem(name: "Sandwich", price: 5.0)
    ]

    @State private var order: [MenuItem] = []

    var body: some View {
        NavigationView {
            VStack {
                List(menuItems) { item in
                    HStack {
                        Text(item.name)
                        Spacer()
                        Text(String(format: "%.2f €", item.price))
                        Button(action: { addItem(item) }) {
                            Image(systemName: "plus.circle")
                        }
                        .buttonStyle(BorderlessButtonStyle())
                    }
                }

                Divider()

                VStack(alignment: .leading) {
                    Text("Bestellung")
                        .font(.headline)
                    ForEach(order) { item in
                        HStack {
                            Text(item.name)
                            Spacer()
                            Text(String(format: "%.2f €", item.price))
                        }
                    }
                    HStack {
                        Text("Gesamt")
                            .bold()
                        Spacer()
                        Text(String(format: "%.2f €", orderTotal))
                            .bold()
                    }
                }
                .padding()
            }
            .navigationTitle("Gastrokasse")
        }
    }

    private var orderTotal: Double {
        order.reduce(0) { $0 + $1.price }
    }

    private func addItem(_ item: MenuItem) {
        order.append(item)
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
