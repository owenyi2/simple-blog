---
date: 2026-02-24
title: "Tinyhouse Chess Engine Part I: Introduction"
---
Code: https://github.com/owenyi2/tinyhouse
# Rules

[Tinyhouse](https://www.chess.com/variants/tinyhouse) is a chess variant played on a 4x4 board using the following pieces
- King: Same as in regular chess 
- Wazir: Moves 1 step orthogonally
- Xiangqi Ma: Moves as a chess Knight however can be ["tripped"](https://en.wikipedia.org/wiki/Xiangqi#Horse) (i.e. blocked) by an orthogonally adjacent piece 
	- ![|253](./Attachments/Tinyhouse%20Chess%20Engine%20Part%20I%20-%20Introduction-1773622469860.webp)
- Ferz: Moves 1 step diagonally
- Pawn: Same as in regular chess, however it cannot move ahead 2 spaces and en passant does not apply. The pawn may still promote to the Wazir, Ma, or Ferz upon reaching the end rank.
The board has the following initial position
![|256](./Attachments/Tinyhouse%20Chess%20Engine%20Part%20I%20-%20Introduction-1773622497561.webp)

Same as in [Crazyhouse](https://www.chess.com/variants/crazyhouse), captured pieces are added to your piece bank and can be dropped on an empty square.
- Captured pawns can not be placed on the first or last ranks.
- Pieces produced by promotion when captured turn back into pawns.

# Motivation

Tinyhouse, being "tiny" with fewer squares and fewer pieces makes it a gentle introduction to [Chess Programming](https://www.chessprogramming.org/Getting_Started). In this blog, we will be using bitboards to implement move generation.

## Additional Niceties of Tinyhouse

1. No [Castling](https://www.chessprogramming.org/Castling) and no [En Passant](https://www.chessprogramming.org/En_passant)
	- In regular chess programming En Passant and Castling require particular care to implement correctly. Below is a snippet from the entry regarding En Passant 
	  > First, the target square of the en passant capture is not identical with origin of the captured pawn, opposed to all other captures. Second, the double pawn push, which triggered the immediate possibility of an en passant capture, must be part of the chess position 
2. Sliding Pieces
	- In regular chess [Sliding Pieces](https://www.chessprogramming.org/Sliding_Pieces) cause some subtle issues for move generation
		- Sliding pieces can be blocked
			- To account for this, a Bitboard technique called [Magical Bitboards](https://analog-hors.github.io/site/magic-bitboards/) was developed
			- Since our Ferz and Wazir only move 1 square adjacent, we do not need to handle blocking
			- However the Xiangqi Ma can be blocked and so we will have the chance to use this technique in our engine
		- Suppose a white King on a2 is checked by a black Rook on a8. The black Rook does not control the a1 square currently because the King blocks it moving the King to a1 is an illegal move because this unblocks the black Rook.
			- We will see a similar issue when implementing the Xiangqi Ma
			- The solution is fairly simple and involves omitting the King when considering blockers
		- Sliding pieces allow pins and discovered checks 
3. 4x4 Bitboards fit inside a `u16` type

# Resources I Found Super Helpful

- [Chess Programming Wiki](https://www.chessprogramming.org/Getting_Started) Wiki
- [Chess Programming](https://www.youtube.com/watch?v=ubX5lyIQoSs&list=PLmN0neTso3Jxh8ZIylk74JpwfiWNI76Cs&index=28) Youtube Channel
- [Analog Hors](https://analog-hors.github.io/site/magic-bitboards/) blog post

# Bitboards

[Chess Programming Wiki > Bitboards](https://www.chessprogramming.org/Bitboards)

For each square, we store 1 bit Yes/No about a question e.g.
- Does a white piece occupy this square?
- Does a black piece occupy this square?
- Does any piece occupy this square?
- Does a King occupy this square?
- Can a Wazir attack this square?
- ...

We can use bitwise operations to obtain info such as
- "Does any piece occupy this square?" is equivalent to "Does a white piece occupy this square?" bitwise OR "Does a black piece occupy this square?"
- The example below shows this for the initial game state

```
Does a King occupy this square?
A =
0 0 0 1
0 0 0 0
0 0 0 0
1 0 0 0

Does a White piece occupy this square?
B =
0 0 0 0
0 0 0 0
1 0 0 0
1 1 1 1

Does a White King occupy this square?
A & B = 
0 0 0 0
0 0 0 0
0 0 0 0
1 0 0 0
```

- "Does a Black King occupy this square" is equivalent to "Does a black piece occupy this square?" bitwise AND "Does a King occupy this square?"

To query, set, or, unset a bit at a particular square, we can simply bitshift by `Square` amount and bitwise And Assign or Or Assign to the bitboard.
```rust
macro_rules! get_bit {
    ($bitmap:expr, $square:expr) => {
        $bitmap.0 & (1 << $square as u16) != 0
    };
}
macro_rules! pop_bit {
    ($bitmap:expr, $square:expr) => {
        $bitmap.0 &= !(1 << $square as u16)
    };
}
macro_rules! set_bit {
    ($bitmap:expr, $square:expr) => {
        $bitmap.0 |= (1 << $square as u16)
    };
}
```

To store the game state, we will be using the following struct `GameState`.

```rust
pub struct BitBoard(u16);

pub struct PieceBoards { // 5 x 2 = 10 bytes
    king: BitBoard, // 2 bytes each
    wazir: BitBoard,
    ma: BitBoard,
    ferz: BitBoard,
    pawn: BitBoard,
}

pub struct Occupancies { // 2 x 2 = 4 bytes
    white: BitBoard, // 2 bytes each
    black: BitBoard,
}

pub enum Side { // 1 bit + align to byte = 1 byte
    White,
    Black,
}

pub struct Inventory { // 1 byte
    inventory: u8,
}

pub struct GameState {
    pub bitboards: PieceBoards, // 10 bytes
    pub occupancies: Occupancies, // 4 bytes
    former_pawns: BitBoard, // 2 byte
    pub inventory: [Inventory; 2], // 2 x 1 = 2 bytes
    pub side: Side, // 1 byte
} 
// 19 bytes. Align to 2 bytes => 20 bytes
```

Notes
- `PieceBoards`: One bitboard per piece stores whether a square is occupied by a particular piece regardless of colour
- `Occupancies`: One bitboard per colour stores whether a square is occupied by a particular colour regardless of piece
	- e.g. `occupancies.white & bitboards.wazir` 
- `former_pawns` field is required to implement the rule "Pieces produced by promotion when captured turn back into pawns."
	- We need to know which pieces on the board are secretly promoted pawns
- We'll elaborate on `inventory` later but the TL;DR is
	- only Pawn, Wazir, Ma, Ferz can be in the inventory and we can see that the inventory can only have 0, 1, or 2 of each piece
	- Therefore 2 bits for each of those 4 pieces covers all possible inventories
	- We need to keep inventory for Black and White

We can verify the sizes match what we expect. [Rust Playground](https://play.rust-lang.org/?version=stable&mode=debug&edition=2024&gist=6f2b0a253f150a5ce560c8013516a226)

```rust
use std::mem;

macro_rules! print_size {
    ($($t:ty),*) => {
        $(
            println!("Size of {}: {} bytes", stringify!($t), mem::size_of::<$t>());
        )*
    }
}

fn main() {
    print_size!(BitBoard, PieceBoards, Occupancies, Side, Inventory, GameState);
}
```

# Printing Bitboards for Debugging

We adopt the following convention:
- Given a bitboard like `0b1000_0000_0000_0000`
	- The most significant 4 bits represent the 1st rank while the least significant 4 bits represent the 4th rank
	- Within a rank of 4 bits, the most significant bit represents the "d" file while the least signficant bit represents the "a" file

```rust
pub struct BitBoard(u16);

impl Display for BitBoard {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f)?;
        for rank in 0..4 {
            for file in 0..4 {
                let square = 4 * rank + file;
                if file == 0 {
                    write!(f, "  {} ", 4 - rank)?;
                }
                write!(f, " {}", get_bit!(self, square) as u8)?;
            }
            writeln!(f)?;
        }
        writeln!(f, "\n     a b c d")?;
        Ok(())
    }
}
```


# Iterating through a Bitboard

We can obtain the position of the least significant set bit using a trick with 2's complement subtraction.

E.g. suppose we have `x = 0b0000_0100_1000_0000`. The position of the least significant bit is 7 (0-index) from the right.
- `-x = 0b1111_1011_1000_0000`. This flips all the bits more significant than the least significant set bit
- `x & -x = 0000000010000000`. Bitwise and kills all the more significant bits since they have flipped. This isolates the least significant bit
- `(x & -x) - 1 = 0000000001111111`. Produces a bunch of 1's up to where the previous bit was. We can call `count_ones()` to obtain the index of `7`

Now to iterate through a bitboard, we find the index using `get_ls1b_index`, pop it from the bitboard and return that index.

```rust
fn get_ls1b_index(bitboard: BitBoard) -> Square {
    assert!(bitboard.0 != 0);
    let idx = ((bitboard.0 & bitboard.0.wrapping_neg()).wrapping_sub(1)).count_ones() as u32;
    Square::from(idx)
}

impl Iterator for BitBoard {
    type Item = Square; // square index

    fn next(&mut self) -> Option<Self::Item> {
        if self.0 == 0 {
            return None;
        }

        let idx = get_ls1b_index(*self);
        pop_bit!(self, idx);

        Some(Square::from(idx))
    }
}
```